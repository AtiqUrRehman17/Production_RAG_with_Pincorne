"""Load and check a golden dataset: test questions with their correct answers and sources.

Expected sources are written as file + section (or file + page), never chunk IDs,
so the dataset stays valid when documents are re-chunked or re-uploaded.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from utils.exceptions import RAGError

QUESTION_TYPES = (
    "clear",            # direct question about one section
    "reworded",         # uses different words than the document
    "unusual-wording",  # odd grammar, typos, very short
    "two-part",         # needs two separate facts or sections
    "table",            # answer lives in a table
    "specific-doc",     # names the document it is about
    "unanswerable",     # on-topic, but the documents don't say
    "off-topic",        # nothing to do with the documents
    "follow-up",        # only makes sense with the chat history
)
UNANSWERABLE_TYPES = ("unanswerable", "off-topic")


class DatasetError(RAGError):
    """The dataset file is missing, not valid JSON, or has incomplete items."""


@dataclass(frozen=True)
class ExpectedSource:
    file: str
    section: str | None = None  # matches if the passage's section contains this text
    page: int | None = None  # matches if the passage covers this page

    def describe(self) -> str:
        where = f'"{self.section}"' if self.section else f"page {self.page}"
        return f"{self.file} {where}"


@dataclass(frozen=True)
class HistoryTurn:
    question: str
    answer: str


@dataclass(frozen=True)
class EvalItem:
    id: str
    question: str
    type: str
    answerable: bool
    expected_answer: str | None = None
    # Each fact is a list of accepted spellings; the answer must contain one of them
    key_facts: tuple[tuple[str, ...], ...] = ()
    # Every source needed for a complete answer (used for recall)
    expected_sources: tuple[ExpectedSource, ...] = ()
    # Other sources that also contain the answer (count as useful, not required)
    also_acceptable: tuple[ExpectedSource, ...] = ()
    history: tuple[HistoryTurn, ...] = ()
    notes: str = ""

    @property
    def useful_sources(self) -> tuple[ExpectedSource, ...]:
        return self.expected_sources + self.also_acceptable


@dataclass
class Dataset:
    name: str
    version: int
    description: str
    documents: list[str]
    items: list[EvalItem] = field(default_factory=list)
    path: Path | None = None

    @property
    def label(self) -> str:
        return f"{self.name}_v{self.version}"


def _source(raw: dict, where: str, problems: list[str]) -> ExpectedSource | None:
    if not isinstance(raw, dict) or not raw.get("file"):
        problems.append(f"{where}: each source needs a 'file'")
        return None
    if not raw.get("section") and raw.get("page") is None:
        problems.append(f"{where}: source '{raw['file']}' needs a 'section' or a 'page'")
        return None
    return ExpectedSource(file=raw["file"], section=raw.get("section"), page=raw.get("page"))


def _key_facts(raw: list, where: str, problems: list[str]) -> tuple[tuple[str, ...], ...]:
    facts = []
    for fact in raw:
        options = [fact] if isinstance(fact, str) else fact
        if not isinstance(options, list) or not options or not all(isinstance(o, str) and o.strip() for o in options):
            problems.append(f"{where}: each key fact must be text or a list of alternative texts")
            continue
        facts.append(tuple(options))
    return tuple(facts)


def _item(raw: dict, index: int, problems: list[str]) -> EvalItem | None:
    item_id = raw.get("id") or f"item #{index + 1}"
    where = f"[{item_id}]"
    missing = [f for f in ("id", "question", "type", "answerable") if f not in raw]
    if missing:
        problems.append(f"{where}: missing {', '.join(repr(f) for f in missing)}")
        return None

    kind, answerable = raw["type"], raw["answerable"]
    if kind not in QUESTION_TYPES:
        problems.append(f"{where}: unknown type '{kind}' (allowed: {', '.join(QUESTION_TYPES)})")
    if not isinstance(answerable, bool):
        problems.append(f"{where}: 'answerable' must be true or false")
    if kind in UNANSWERABLE_TYPES and answerable:
        problems.append(f"{where}: type '{kind}' must have answerable: false")

    sources = tuple(s for s in (_source(r, where, problems) for r in raw.get("expected_sources", [])) if s)
    acceptable = tuple(s for s in (_source(r, where, problems) for r in raw.get("also_acceptable", [])) if s)
    facts = _key_facts(raw.get("key_facts", []), where, problems)

    if answerable:
        if not raw.get("expected_answer"):
            problems.append(f"{where}: answerable items need an 'expected_answer'")
        if not facts:
            problems.append(f"{where}: answerable items need at least one key fact")
        if not sources:
            problems.append(f"{where}: answerable items need at least one expected source")
    elif sources or facts:
        problems.append(f"{where}: unanswerable items must not have sources or key facts")

    history = []
    for turn in raw.get("history", []):
        if not isinstance(turn, dict) or not turn.get("question") or not turn.get("answer"):
            problems.append(f"{where}: each history turn needs a 'question' and an 'answer'")
        else:
            history.append(HistoryTurn(turn["question"], turn["answer"]))
    if kind == "follow-up" and not history:
        problems.append(f"{where}: follow-up items need a 'history'")

    return EvalItem(
        id=raw["id"],
        question=raw["question"],
        type=kind,
        answerable=bool(answerable),
        expected_answer=raw.get("expected_answer"),
        key_facts=facts,
        expected_sources=sources,
        also_acceptable=acceptable,
        history=tuple(history),
        notes=raw.get("notes", ""),
    )


def load_dataset(path: Path) -> Dataset:
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"Dataset not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{path.name} is not valid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc

    problems: list[str] = []
    items = [_item(r, i, problems) for i, r in enumerate(raw.get("items", []))]
    items = [i for i in items if i]

    if not items and not problems:
        problems.append("the dataset has no items")
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            problems.append(f"[{item.id}]: duplicate id")
        seen.add(item.id)

    documents = raw.get("documents", [])
    for item in items:
        for source in item.useful_sources:
            if documents and source.file not in documents:
                problems.append(f"[{item.id}]: source file '{source.file}' is not in the dataset's 'documents' list")

    if problems:
        listed = "\n  - ".join(problems)
        raise DatasetError(f"{path.name} has {len(problems)} problem(s):\n  - {listed}")

    return Dataset(
        name=raw.get("name", path.stem),
        version=int(raw.get("version", 1)),
        description=raw.get("description", ""),
        documents=documents,
        items=items,
        path=path,
    )
