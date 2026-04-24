from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from agent.schemas.core import Turn


class BufferMemory:
    """Short-term per-session buffer, analogue of LangChain's ConversationBufferMemory.

    Data is partitioned by ``session_id`` — new session starts with an empty buffer.
    Thread-safe enough for the single-process benchmark; no cross-process durability.
    """

    name = "buffer"

    def __init__(self, max_turns: int = 12):
        self.max_turns = max_turns
        self._store: dict[str, deque[Turn]] = defaultdict(lambda: deque(maxlen=self.max_turns))

    def health(self) -> bool:
        return True

    def write(self, obj: Turn, **_: Any) -> Turn:
        if not isinstance(obj, Turn):
            raise TypeError(f"BufferMemory only accepts Turn, got {type(obj)}")
        self._store[obj.session_id].append(obj)
        return obj

    def read(self, session_id: str, **_: Any) -> list[Turn]:
        return list(self._store.get(session_id, ()))

    def search(self, query: str, k: int = 5, session_id: str | None = None, **_: Any) -> list[Turn]:
        if not session_id:
            return []
        q = query.lower()
        hits = [t for t in self._store.get(session_id, ()) if q in t.content.lower()]
        return hits[-k:]

    def delete(self, session_id: str | None = None, **_: Any) -> bool:
        if session_id is None:
            self._store.clear()
        else:
            self._store.pop(session_id, None)
        return True

    def recent(self, session_id: str, k: int) -> list[Turn]:
        return list(self._store.get(session_id, ()))[-k:]
