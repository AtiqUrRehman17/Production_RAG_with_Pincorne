"""Grounded question answering: rewrite -> retrieve -> answer -> check citations.

  1. Follow-up questions ("what about the second one?") are rewritten into a
     standalone question using the chat history, so search can find them.
  2. The retriever searches the user's documents. If nothing relevant is found,
     the LLM is not called at all and the "not found" answer is returned.
  3. The LLM (LLM_PROVIDER: Gemini or Groq) answers from numbered sources and
     cites them like [1] (streamed).
  4. Citations are checked: numbers that don't match a real source are reported.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from llm.chat_model import get_chat_model
from prompts.rag_prompts import NOT_FOUND_ANSWER, answer_prompt, format_sources, rewrite_prompt
from retrieval.citations import source_label
from retrieval.retriever import DocumentRetriever
from utils.config import Settings
from utils.exceptions import LLMError
from utils.logger import get_logger
from utils.tracing import traced

logger = get_logger(__name__)

# Matches [1], [2, 3] and [2][3] (the last as two matches). Up to 3 digits, so a
# bracketed year like [2024] in the answer isn't mistaken for a citation.
_CITATION = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")
# Some models (e.g. gpt-oss on Groq) cite with 【1】 instead of [1]
_CITATION_BRACKETS = str.maketrans("【】", "[]")
# ...and add line references like [2†L1-L4]; only the source number is kept
_CITATION_EXTRA = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)†[^\]\n]*\]")
# An unclosed "[" is held back at most this long while waiting for its "]"
_MAX_HELD_CHARS = 40


class _CitationCleaner:
    """Rewrites model-specific citation formats to [n] while the answer streams.

    A citation can arrive split over several tokens ("[2", "†L1", "-L4]"), so
    text from an unclosed "[" is held back until its "]" arrives."""

    def __init__(self) -> None:
        self._held = ""

    def feed(self, token: str) -> str:
        text = self._held + token.translate(_CITATION_BRACKETS)
        start = text.rfind("[")
        if start != -1 and "]" not in text[start:] and len(text) - start <= _MAX_HELD_CHARS:
            text, self._held = text[:start], text[start:]
        else:
            self._held = ""
        return _CITATION_EXTRA.sub(r"[\1]", text)

    def flush(self) -> str:
        text, self._held = self._held, ""
        return _CITATION_EXTRA.sub(r"[\1]", text)

# A rewritten follow-up longer than this, or on several lines, is an answer, not a question
_MAX_REWRITE_CHARS = 300
# Earlier answers are shortened in the rewrite prompt; the start names the topic
_MAX_HISTORY_ANSWER_CHARS = 600


def _is_single_question(text: str) -> bool:
    return bool(text) and "\n" not in text and "```" not in text and len(text) <= _MAX_REWRITE_CHARS


@dataclass
class Citation:
    number: int
    label: str
    passage: Document


@dataclass
class Answer:
    question: str
    standalone_question: str
    text: str
    found: bool  # False when the documents don't answer the question
    citations: list[Citation] = field(default_factory=list)
    invalid_citation_numbers: list[int] = field(default_factory=list)
    passages: list[Document] = field(default_factory=list)


@dataclass
class ChatTurn:
    question: str
    answer: str


def cited_numbers(text: str) -> list[int]:
    numbers: list[int] = []
    for match in _CITATION.finditer(text):
        for part in match.group(1).split(","):
            number = int(part)
            if number not in numbers:
                numbers.append(number)
    return numbers


def strip_citations(text: str) -> str:
    return re.sub(r"\s*" + _CITATION.pattern, "", text)


def _trace_inputs(inputs: dict) -> dict:
    """What the trace shows as the input of a whole question."""
    return {
        "question": inputs.get("question"),
        "history": [{"question": t.question, "answer": t.answer} for t in inputs.get("history") or ()],
    }


def _trace_outputs(answer: Answer) -> dict:
    """What the trace shows as the result of a whole question."""
    return {
        "answer": answer.text,
        "found": answer.found,
        "searched_for": answer.standalone_question,
        "citations": [f"[{c.number}] {c.label}" for c in answer.citations],
        "invalid_citations": answer.invalid_citation_numbers,
        "passages": len(answer.passages),
    }


class RAGChain:
    def __init__(self, user_id: str, settings: Settings, document_ids: list[str] | None = None):
        self.settings = settings
        self.retriever = DocumentRetriever.for_user(user_id, settings, document_ids)
        # run_name = the step's name in LangSmith traces
        self.answer_chain = (answer_prompt | get_chat_model()).with_config(run_name="answer")
        # Rewriting is a simple task, so it runs with minimal thinking for speed (Gemini)
        self.rewrite_chain = (rewrite_prompt | get_chat_model(thinking_level="minimal")).with_config(
            run_name="rewrite"
        )

    # One trace per question: rewrite, retrieval and answer appear as its steps
    @traced(name="ask", run_type="chain", process_inputs=_trace_inputs, process_outputs=_trace_outputs)
    def ask(
        self,
        question: str,
        history: Sequence[ChatTurn] = (),
        on_token: Callable[[str], None] | None = None,
    ) -> Answer:
        max_turns = self.settings.chat_history_turns
        turns = list(history)[-max_turns:] if max_turns else []
        messages = self._history_messages(turns)

        standalone = self._rewrite(question, turns) if turns else question
        passages = self.retriever.invoke(standalone)  # raises clear errors itself

        if not passages:
            logger.info("No relevant passages; skipping the LLM")
            if on_token:
                on_token(NOT_FOUND_ANSWER)
            return Answer(question, standalone, NOT_FOUND_ANSWER, found=False)

        text = self._generate(standalone, passages, messages, on_token)
        return self._build_answer(question, standalone, text, passages)

    @staticmethod
    def _history_messages(history: list[ChatTurn]) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for turn in history:
            messages.append(HumanMessage(turn.question))
            # Old citation numbers refer to old sources, so remove them
            messages.append(AIMessage(strip_citations(turn.answer)))
        return messages

    @staticmethod
    def _conversation_text(turns: list[ChatTurn]) -> str:
        lines = []
        for turn in turns:
            answer = " ".join(strip_citations(turn.answer).split())
            if len(answer) > _MAX_HISTORY_ANSWER_CHARS:
                answer = answer[:_MAX_HISTORY_ANSWER_CHARS] + "..."
            lines += [f"User: {turn.question}", f"Assistant: {answer}"]
        return "\n".join(lines)

    @staticmethod
    def _fallback_query(question: str, turns: list[ChatTurn]) -> str:
        # The previous question names what "it" / "that" refers to, so searching
        # with both is far better than the bare follow-up
        return f"{turns[-1].question} {question}"

    def _rewrite(self, question: str, turns: list[ChatTurn]) -> str:
        try:
            result = self.rewrite_chain.invoke(
                {"conversation": self._conversation_text(turns), "question": question}
            )
        except Exception:
            logger.warning("Question rewrite failed; searching with the previous question added",
                           exc_info=True)
            return self._fallback_query(question, turns)

        rewritten = result.text.strip().removeprefix("Standalone question:").strip().strip('"')
        if not _is_single_question(rewritten):
            # The model answered (several lines, a long text) instead of rewriting
            logger.warning("Rewrite looked like an answer, not a question; searching with the "
                           "previous question added. Got: %r", rewritten[:120])
            return self._fallback_query(question, turns)
        logger.info("Rewrote question: %r -> %r", question, rewritten)
        return rewritten

    def _generate(
        self,
        question: str,
        passages: list[Document],
        messages: list[BaseMessage],
        on_token: Callable[[str], None] | None,
    ) -> str:
        inputs = {"sources": format_sources(passages), "history": messages, "question": question}
        parts: list[str] = []
        cleaner = _CitationCleaner()

        def emit(token: str) -> None:
            if token:
                parts.append(token)
                if on_token:
                    on_token(token)

        try:
            for chunk in self.answer_chain.stream(inputs):
                emit(cleaner.feed(chunk.text))
            emit(cleaner.flush())
        except Exception as exc:
            logger.error("Answer generation failed: %s", exc)
            logger.debug("Answer generation failure details", exc_info=True)
            raise self._generation_error(exc) from exc

        text = "".join(parts).strip()
        if not text:
            raise LLMError(f"{self.settings.llm_model} returned an empty answer.")
        return text

    def _generation_error(self, exc: Exception) -> LLMError:
        model = self.settings.llm_model
        message = str(exc)
        if self.settings.llm_provider == "groq":
            if "429" in message or "rate_limit" in message.lower():
                return LLMError(
                    f"Groq's rate limit for {model} was reached (429). Free-tier limits are per "
                    "minute and per day (daily limits reset at midnight UTC); check them at "
                    "console.groq.com/settings/limits."
                )
            return LLMError(
                f"Groq could not generate an answer with {model}. "
                "Check GROQ_API_KEY, GROQ_LLM_MODEL, your limits and your internet connection."
            )
        if "RESOURCE_EXHAUSTED" in message:
            return LLMError(
                f"Gemini's request quota for {model} is used up "
                "(429 RESOURCE_EXHAUSTED). Free-tier daily limits reset at midnight Pacific "
                "time; check your limits in Google AI Studio, or enable billing for higher limits."
            )
        return LLMError(
            "Gemini could not generate an answer. "
            "Check GEMINI_API_KEY, GEMINI_LLM_MODEL, your quota and your internet connection."
        )

    @staticmethod
    def _build_answer(question: str, standalone: str, text: str, passages: list[Document]) -> Answer:
        if text.startswith(NOT_FOUND_ANSWER) and len(text) <= len(NOT_FOUND_ANSWER) + 5:
            return Answer(question, standalone, text, found=False, passages=passages)

        citations, invalid = [], []
        for number in cited_numbers(text):
            if 1 <= number <= len(passages):
                passage = passages[number - 1]
                citations.append(Citation(number, source_label(passage.metadata), passage))
            else:
                invalid.append(number)

        if invalid:
            logger.warning("Answer cited sources that don't exist: %s", invalid)
        if not citations:
            logger.warning("Answer has no citations")
        citations.sort(key=lambda c: c.number)
        return Answer(question, standalone, text, True, citations, invalid, passages)
