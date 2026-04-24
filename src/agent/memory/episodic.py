from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agent.schemas.memory import Episode


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class EpisodicMemory:
    """Append-only JSONL log of episodes. Read path: in-memory scan + tag filter.

    Files roll monthly (``episodes_YYYYMM.jsonl``). Reads load all rolling files
    for the caller — good enough for Lab 17; scaling left to later labs.
    """

    name = "episodic"

    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    # ---------- protocol ----------

    def health(self) -> bool:
        return self.log_dir.exists()

    def write(self, obj: Episode, **_: Any) -> Episode:
        path = self._current_file(obj.ts)
        with path.open("a", encoding="utf-8") as f:
            f.write(obj.model_dump_json() + "\n")
        return obj

    def read(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 100,
        **_: Any,
    ) -> list[Episode]:
        out: list[Episode] = []
        for ep in self._iter_all():
            if user_id and ep.user_id != user_id:
                continue
            if session_id and ep.session_id != session_id:
                continue
            if kind and ep.kind != kind:
                continue
            out.append(ep)
        return out[-limit:]

    def search(
        self,
        query: str,
        k: int = 5,
        user_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        **_: Any,
    ) -> list[Episode]:
        q_tokens = {t for t in _tokenize(query.lower()) if len(t) > 2}
        scored: list[tuple[float, Episode]] = []
        for ep in self._iter_all():
            if user_id and ep.user_id != user_id:
                continue
            hay = (ep.summary + " " + (ep.context_excerpt or "") + " " + " ".join(ep.tags)).lower()
            hay_tokens = set(_tokenize(hay))
            score = 0.0
            overlap = q_tokens & hay_tokens
            if overlap:
                score += len(overlap)
            if tags:
                score += sum(1.0 for t in tags if t in ep.tags)
            if score > 0:
                scored.append((score, ep))
        scored.sort(key=lambda x: (-x[0], x[1].ts))
        return [ep for _, ep in scored[:k]]

    def delete(self, **_: Any) -> bool:
        # Episodic is immutable by design; delete() is a no-op returning False.
        return False

    def clear(self) -> None:
        """Test helper. Not part of the protocol."""
        for p in self.log_dir.glob("episodes_*.jsonl"):
            p.unlink()

    # ---------- helpers ----------

    def _current_file(self, ts: datetime) -> Path:
        return self.log_dir / f"episodes_{ts.strftime('%Y%m')}.jsonl"

    def _iter_all(self):
        for path in sorted(self.log_dir.glob("episodes_*.jsonl")):
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield Episode.model_validate_json(line)
                    except Exception:
                        continue
