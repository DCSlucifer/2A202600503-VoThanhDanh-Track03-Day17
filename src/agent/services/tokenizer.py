"""Token counting with tiktoken, falling back to a length heuristic."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

try:
    import tiktoken  # type: ignore
    _HAVE_TIKTOKEN = True
except Exception:
    _HAVE_TIKTOKEN = False


@lru_cache(maxsize=8)
def get_tokenizer(model: str = "gpt-4o-mini"):  # type: ignore[override]
    if not _HAVE_TIKTOKEN:
        return None
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None


def count_tokens(text: str, model: Optional[str] = None) -> int:
    if not text:
        return 0
    enc = get_tokenizer(model or "gpt-4o-mini")
    if enc is None:
        # fallback heuristic: 4 chars per token
        return max(1, len(text) // 4)
    try:
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)
