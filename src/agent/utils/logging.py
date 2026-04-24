from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class JsonlLogger:
    """Append-only JSONL logger that is safe across threads in one process."""

    _locks: dict[str, threading.Lock] = {}

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = JsonlLogger._locks.setdefault(str(self.path.resolve()), threading.Lock())

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, default=_json_default, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return str(obj)
