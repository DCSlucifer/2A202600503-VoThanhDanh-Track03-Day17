"""Deterministic template summarizer + optional LLM summarizer.

Lab 17 keeps the default deterministic so benchmark stays byte-stable.
"""
from __future__ import annotations

from typing import Callable, Optional

from agent.schemas.context import ContextItem


class Summarizer:
    def __init__(self, llm_summarize: Optional[Callable[[str], str]] = None):
        self._llm = llm_summarize

    def condense_pair(self, user: str, assistant: str) -> str:
        u = _short(user, 80)
        a = _short(assistant, 80)
        return f"- user asked: {u}; assistant answered: {a}"

    def compress_items(self, items: list[ContextItem]) -> str:
        if not items:
            return ""
        lines = []
        for it in items:
            frag = _short(it.text, 120)
            src = it.source
            sid = it.source_id or it.item_id
            lines.append(f"- [{src}:{sid}] {frag}")
        return "\n".join(lines)

    def llm_summarize(self, text: str) -> str:
        if self._llm is None:
            return _short(text, 160)
        try:
            return self._llm(text)
        except Exception:
            return _short(text, 160)


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
