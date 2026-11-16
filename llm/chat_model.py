"""The chat model that writes answers and rewrites follow-ups, chosen by LLM_PROVIDER.

  gemini: Google Gemini. Temperature is deliberately left unset: for Gemini 3
          models Google advises keeping the default, as lowering it can cause
          looping and weaker reasoning. Grounding is enforced by the prompt instead.
  groq:   open models (e.g. Llama 3.3 70B) on Groq. A low temperature keeps these
          models close to the sources; they have no thinking levels.

Embeddings are separate and always use Gemini (embeddings/gemini.py).
"""

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from utils.config import get_settings

_MAX_RETRIES = 4  # built-in retries with backoff on rate limits and server errors
_TIMEOUT_SECONDS = 120


@lru_cache
def get_chat_model(thinking_level: str | None = None) -> BaseChatModel:
    """thinking_level: 'minimal' | 'low' | 'medium' | 'high' (None = LLM_THINKING_LEVEL).
    Gemini only; ignored for Groq."""
    settings = get_settings()
    if settings.llm_provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.groq_llm_model,
            api_key=settings.groq_api_key,
            temperature=settings.groq_temperature,
            max_tokens=settings.llm_max_output_tokens,
            max_retries=_MAX_RETRIES,
            timeout=_TIMEOUT_SECONDS,
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_llm_model,
        google_api_key=settings.gemini_api_key,
        max_output_tokens=settings.llm_max_output_tokens,
        thinking_level=thinking_level or settings.llm_thinking_level,
        max_retries=_MAX_RETRIES,
        timeout=_TIMEOUT_SECONDS,
    )
