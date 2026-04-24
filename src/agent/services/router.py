"""Rule-based memory router with intent scoring and ordered fallback.

Designed to be swapped for a classifier later — only the entry point
``route(message, user_id) -> RouterDecision`` is public.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from agent.config import RouterConfig
from agent.schemas.routing import BackendName, IntentName, IntentScore, RouterDecision

_RULES: list[tuple[str, IntentName, float, re.Pattern[str]]] = [
    # preference capture (write, not read)
    ("pref_capture_vn_pos", "preference_capture", 0.95,
     re.compile(r"\bt[ôoóòỏõọơớờởỡợ]i\s+(?:rất\s+)?th[íi]ch\b", re.IGNORECASE)),
    ("pref_capture_vn_neg", "preference_capture", 0.95,
     re.compile(r"\b(?:kh[oô]ng\s+th[íi]ch|gh[eé]t)\b", re.IGNORECASE)),
    ("pref_capture_en_pos", "preference_capture", 0.95,
     re.compile(r"\bi\s+(?:really\s+)?(?:like|prefer|love)\s+\w", re.IGNORECASE)),
    ("pref_capture_en_neg", "preference_capture", 0.95,
     re.compile(r"\bi\s+(?:dislike|hate|don'?t\s+like)\b", re.IGNORECASE)),

    # factual capture (write, not read)
    ("fact_capture_allergy_vn", "fact_capture", 0.95,
     re.compile(r"^\s*(?:[àa]\s+nhầm,?\s*)?(?:t[ôo]i|m[iì]nh|toi|minh)\s+"
                r"(?:dị\s+ứng|di\s+ung)\s+(?!gì\b|gi\b)",
                re.IGNORECASE)),
    ("fact_capture_allergy_en", "fact_capture", 0.95,
     re.compile(r"^\s*(?:i(?:'m| am)? allergic to|my allergy is)\s+(?!what\b|which\b)",
                re.IGNORECASE)),
    ("fact_capture_profile", "fact_capture", 0.9,
     re.compile(r"^\s*(my name is|my role is|my job is|i(?:'m| am)? using|"
                r"t[ôo]i đang dùng|tên (?:của )?t[ôo]i|vai trò của t[ôo]i là)\b",
                re.IGNORECASE)),

    # preference recall
    ("pref_recall_which_language", "preference_recall", 0.9,
     re.compile(r"\b(which|what).{0,12}(language|framework|tool)\b", re.IGNORECASE)),
    ("pref_recall_what_do_i_prefer", "preference_recall", 0.9,
     re.compile(r"\bwhat do i (?:prefer|like)\b", re.IGNORECASE)),
    ("pref_recall_vn", "preference_recall", 0.85,
     re.compile(r"\b(t[ôoóòỏõọơớờởỡợ]i|m[iì]nh)\s+th[íi]ch\s+(?:ng[oô]n ng[uữ]|c[aá]i n[aà]o)\b",
                re.IGNORECASE)),
    ("pref_recall_soft", "preference_recall", 0.55,
     re.compile(r"\b(prefer|preference|yêu thích|ưu tiên)\b", re.IGNORECASE)),

    # factual recall
    ("fact_recall_my_role", "factual_recall", 0.9,
     re.compile(r"\bmy (role|job|project|team|name|company)\b", re.IGNORECASE)),
    ("fact_recall_remind_me", "factual_recall", 0.85,
     re.compile(r"\b(remind me|tell me again|nh[aắ]c l[aạ]i|nh[oớ] l[aạ]i)\b", re.IGNORECASE)),
    ("fact_recall_what_am_i", "factual_recall", 0.8,
     re.compile(r"\bwhat('?s| is) my\b", re.IGNORECASE)),
    ("fact_recall_using", "factual_recall", 0.55,
     re.compile(r"\b(using|version|config|stack)\b", re.IGNORECASE)),
    ("fact_recall_allergy", "factual_recall", 0.9,
     re.compile(r"\b(allerg(?:y|ic)|d[ịi]\s*[ứu]ng|di\s+ung)\b", re.IGNORECASE)),

    # experience recall
    ("exp_recall_before", "experience_recall", 0.9,
     re.compile(r"\b(have i|did i|last time|previously|tr[uư][oớ]c đây|l[aà]n tr[uư][oớ]c)\b",
                re.IGNORECASE)),
    ("exp_recall_confused", "experience_recall", 0.7,
     re.compile(r"\b(async[/ ]?await|asyncio|promises|concurrency|recursion|pointer)\b",
                re.IGNORECASE)),
]


@dataclass
class RouteOutput:
    decision: RouterDecision


class MemoryRouter:
    def __init__(self, cfg: RouterConfig):
        self.cfg = cfg

    def route(self, user_message: str, known_intents: dict[str, float] | None = None) -> RouterDecision:
        t0 = time.perf_counter()
        scores: dict[IntentName, float] = {}
        matched: list[str] = []

        for name, intent, weight, pattern in _RULES:
            if pattern.search(user_message):
                scores[intent] = max(scores.get(intent, 0.0), weight)
                matched.append(name)

        if known_intents:
            for k, v in known_intents.items():
                if k in scores:
                    scores[k] = max(scores[k], v)  # type: ignore[index]

        # default task intent always present as a baseline
        scores.setdefault("task_default", 0.3)

        intents = sorted(
            (IntentScore(name=n, score=s) for n, s in scores.items()),
            key=lambda x: -x.score,
        )

        backends = self._backends_for(intents)

        # hard cap
        if len(backends) > self.cfg.max_backends_per_turn:
            backends = backends[: self.cfg.max_backends_per_turn]

        fallback_used = False

        elapsed = (time.perf_counter() - t0) * 1000.0

        return RouterDecision(
            input=user_message,
            intents=intents,
            backends=backends,  # type: ignore[arg-type]
            fallback_used=fallback_used,
            elapsed_ms=round(elapsed, 3),
            matched_rules=matched,
        )

    def _backends_for(self, intents: list[IntentScore]) -> list[BackendName]:
        hi = self.cfg.high_confidence_threshold
        mid = self.cfg.medium_confidence_threshold
        chosen: list[BackendName] = ["buffer"]  # buffer always included

        top = intents[0] if intents else None
        if top is None:
            return chosen

        def add(*bs: BackendName) -> None:
            for b in bs:
                if b not in chosen:
                    chosen.append(b)

        if top.score >= hi:
            if top.name == "preference_recall":
                add("redis_pref", "semantic")
            elif top.name == "factual_recall":
                add("redis_fact", "semantic")
            elif top.name == "experience_recall":
                add("episodic", "semantic")
            elif top.name == "preference_capture":
                # no read needed; keep buffer
                pass
            elif top.name == "fact_capture":
                # no read needed; persist node extracts facts after the response
                pass
            else:  # task_default
                add("semantic")
        elif top.score >= mid:
            # fan out top-2
            primary = top.name
            secondary = intents[1].name if len(intents) > 1 else None
            for intent in filter(None, (primary, secondary)):
                if intent == "preference_recall":
                    add("redis_pref", "semantic")
                elif intent == "factual_recall":
                    add("redis_fact", "semantic")
                elif intent == "experience_recall":
                    add("episodic", "semantic")
                elif intent == "fact_capture":
                    pass
                elif intent == "task_default":
                    add("semantic")
        else:
            # Plain task-default turns should not pull unrelated long-term memory.
            # Explicit recall intents above opt into Redis/episodic/semantic.
            pass

        return chosen
