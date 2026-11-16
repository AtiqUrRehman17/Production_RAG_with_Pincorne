"""Token counting.

Gemini's own tokenizer needs an API call, so we use tiktoken's cl100k_base as a
fast local estimate. It is close enough for sizing chunks.
"""

from functools import lru_cache

import tiktoken

TOKEN_ENCODING = "cl100k_base"


@lru_cache
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(TOKEN_ENCODING)


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text, disallowed_special=()))
