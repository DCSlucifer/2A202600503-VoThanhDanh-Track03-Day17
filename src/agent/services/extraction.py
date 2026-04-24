from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agent.schemas.core import Turn
from agent.schemas.memory import Fact, Preference
from agent.services.runtime.base import LLMRuntime


@dataclass
class ExtractionResult:
    preferences: list[Preference] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


class LLMStructuredExtractor:
    """Optional LLM-based memory extractor with strict JSON parsing.

    The graph defaults to deterministic rule extractors for tests/benchmarks.
    This class is the production extension hook for richer extraction when
    `settings.memory.extraction_mode == "llm"`.
    """

    _ALLOWED_PREF_KEYS = {"language.liked", "language.disliked", "tone"}
    _ALLOWED_FACT_IDS = {
        "profile.allergy",
        "profile.name",
        "profile.role",
        "profile.stack",
    }

    def __init__(self, runtime: LLMRuntime):
        self.runtime = runtime

    def extract(self, turn: Turn, user_id: str) -> ExtractionResult:
        if turn.role != "user":
            return ExtractionResult()
        prompt = (
            "Extract durable user memory from the message. Return only JSON with "
            "keys preferences and facts. Preferences use key/value/confidence. "
            "Facts use fact_id, predicate, object, confidence, tags. "
            "Allowed fact_id values: profile.allergy, profile.name, profile.role, profile.stack.\n"
            f"Message: {turn.content}"
        )
        try:
            response = self.runtime.generate(prompt)
        except Exception as exc:
            return ExtractionResult(errors=[{"kind": "runtime", "message": str(exc)}])
        return self.parse(response.content, turn=turn, user_id=user_id)

    def parse(self, content: str, *, turn: Turn, user_id: str) -> ExtractionResult:
        try:
            payload = json.loads(_extract_json_object(content))
        except Exception as exc:
            return ExtractionResult(errors=[{"kind": "parse", "message": str(exc)}])

        preferences: list[Preference] = []
        facts: list[Fact] = []
        errors: list[dict[str, str]] = []

        for raw in payload.get("preferences", []) or []:
            try:
                key = str(raw.get("key", "")).strip()
                if key not in self._ALLOWED_PREF_KEYS:
                    continue
                value = str(raw.get("value", "")).strip().lower()
                if not value:
                    continue
                preferences.append(
                    Preference(
                        user_id=user_id,
                        key=key,
                        value=value,
                        confidence=_confidence(raw.get("confidence")),
                        source_turn_id=turn.turn_id,
                        updated_at=datetime.utcnow(),
                    )
                )
            except Exception as exc:
                errors.append({"kind": "preference", "message": str(exc)})

        for raw in payload.get("facts", []) or []:
            try:
                fact_id = str(raw.get("fact_id", "")).strip()
                if fact_id not in self._ALLOWED_FACT_IDS:
                    continue
                obj = str(raw.get("object", "")).strip()
                if not obj:
                    continue
                facts.append(
                    Fact(
                        fact_id=fact_id,
                        user_id=user_id,
                        subject="user",
                        predicate=str(raw.get("predicate", "has")).strip() or "has",
                        object=obj,
                        confidence=_confidence(raw.get("confidence")),
                        source_turn_id=turn.turn_id,
                        ts=datetime.utcnow(),
                        tags=[str(t) for t in (raw.get("tags") or []) if str(t).strip()],
                    )
                )
            except Exception as exc:
                errors.append({"kind": "fact", "message": str(exc)})

        return ExtractionResult(preferences=preferences, facts=facts, errors=errors)


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("no JSON object found")
    return match.group(0)


def _confidence(value: Any) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return 0.8
    return max(0.0, min(1.0, val))
