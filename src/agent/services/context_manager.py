"""4-level hierarchy context manager with priority-based eviction.

See blueprint §5. Invariants enforced:
  - L0 never shrinks
  - Order of compression: drop L3 → trim L2 → summarize L1 pairs → compress L2
  - Deterministic: no wall-clock within a single assemble() call
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from agent.config import ContextConfig
from agent.schemas.context import ContextItem, ContextPack, Level, PriorityScore
from agent.schemas.core import Turn
from agent.schemas.memory import Episode, Fact, Preference, SemanticChunk
from agent.schemas.routing import RecallResult
from agent.services.summarizer import Summarizer
from agent.services.tokenizer import count_tokens
from agent.utils.ids import new_id


class ContextBudgetError(RuntimeError):
    """Raised when even L0 alone exceeds the token budget."""


@dataclass
class AssembleInputs:
    system_prompt: str
    user_message: str
    buffer: list[Turn]
    recall: Optional[RecallResult]
    pinned_profile: Optional[str] = None  # eg. "User preferences: likes Python, dislikes Java"
    model: str = "gpt-4o-mini"
    now: Optional[datetime] = None


class ContextManager:
    def __init__(self, cfg: ContextConfig, summarizer: Summarizer):
        self.cfg = cfg
        self.summarizer = summarizer

    # ---------- public ----------

    def assemble(self, inputs: AssembleInputs) -> ContextPack:
        now = inputs.now or datetime.utcnow()
        budget = self.cfg.budget_tokens - self.cfg.response_headroom_tokens
        items = self._gather(inputs, now)
        pack = self._finalize(items, budget)

        attempts = 0
        while pack.total_tokens > budget and attempts < 4:
            if attempts == 0:
                items = self._drop_level(items, "L3")
            elif attempts == 1:
                items = self._trim_l2(items, budget)
            elif attempts == 2:
                items = self._summarize_l1(items, inputs.model)
            elif attempts == 3:
                items = self._compress_l2(items)
            pack = self._finalize(items, budget)
            attempts += 1

        if pack.total_tokens > budget:
            # degrade: keep only L0
            l0_only = [it for it in items if it.level == "L0"]
            pack = self._finalize(l0_only, budget)
            pack.degraded = True
            if pack.total_tokens > budget:
                raise ContextBudgetError(
                    f"L0 alone exceeds budget: {pack.total_tokens} > {budget}"
                )
        return pack

    # ---------- gather ----------

    def _gather(self, inp: AssembleInputs, now: datetime) -> list[ContextItem]:
        items: list[ContextItem] = []
        w = self.cfg.weights

        # L0: system + pinned profile + current user message
        sys_text = inp.system_prompt.strip()
        items.append(
            ContextItem(
                item_id="l0_system",
                level="L0",
                source="system",
                source_id="system",
                text=sys_text,
                tokens=count_tokens(sys_text, inp.model),
                score=_score(w, level="L0", recency=1.0, relevance=1.0, pin=1.0),
            )
        )
        if inp.pinned_profile:
            items.append(
                ContextItem(
                    item_id="l0_profile",
                    level="L0",
                    source="preference",
                    source_id="profile",
                    text=inp.pinned_profile.strip(),
                    tokens=count_tokens(inp.pinned_profile, inp.model),
                    score=_score(w, level="L0", recency=1.0, relevance=1.0, pin=1.0),
                )
            )
        user_msg = f"User: {inp.user_message.strip()}"
        items.append(
            ContextItem(
                item_id="l0_user",
                level="L0",
                source="buffer",
                source_id="current_turn",
                text=user_msg,
                tokens=count_tokens(user_msg, inp.model),
                score=_score(w, level="L0", recency=1.0, relevance=1.0, pin=1.0),
            )
        )

        # L1: recent dialogue (last K turns before current)
        recent_n = self.cfg.buffer_recent_turns
        for turn in list(inp.buffer)[-recent_n:]:
            if turn.role == "system":
                continue
            text = f"{turn.role}: {turn.content.strip()}"
            items.append(
                ContextItem(
                    item_id=f"l1_{turn.turn_id}",
                    level="L1",
                    source="buffer",
                    source_id=turn.turn_id,
                    text=text,
                    tokens=count_tokens(text, inp.model),
                    score=_score(
                        w,
                        level="L1",
                        recency=_recency(turn.ts, now, self.cfg.recency_tau_hours),
                        relevance=0.5,
                        pin=0.0,
                    ),
                )
            )

        # L2: recalled memory
        if inp.recall:
            for pref in inp.recall.preferences:
                text = f"[preference] {pref.key} = {pref.value} (conf {pref.confidence:.2f})"
                items.append(
                    ContextItem(
                        item_id=new_id("l2p"),
                        level="L2",
                        source="preference",
                        source_id=pref.key,
                        text=text,
                        tokens=count_tokens(text, inp.model),
                        score=_score(w, level="L2",
                                     recency=_recency(pref.updated_at, now, self.cfg.recency_tau_hours),
                                     relevance=pref.confidence,
                                     pin=0.0),
                    )
                )
            for fact in inp.recall.facts:
                text = f"[fact] {fact.render()} (conf {fact.confidence:.2f})"
                items.append(
                    ContextItem(
                        item_id=new_id("l2f"),
                        level="L2",
                        source="fact",
                        source_id=fact.fact_id,
                        text=text,
                        tokens=count_tokens(text, inp.model),
                        score=_score(w, level="L2",
                                     recency=_recency(fact.ts, now, self.cfg.recency_tau_hours),
                                     relevance=fact.confidence, pin=0.0),
                    )
                )
            for ep in inp.recall.episodes:
                text = f"[episode:{ep.kind}] {ep.summary}"
                if ep.kind == "confusion":
                    text += (
                        " Guidance: the user found this tricky before; explain in "
                        "simple terms, step by step, and keep it beginner-friendly."
                    )
                items.append(
                    ContextItem(
                        item_id=new_id("l2e"),
                        level="L2",
                        source="episode",
                        source_id=ep.episode_id,
                        text=text,
                        tokens=count_tokens(text, inp.model),
                        score=_score(w, level="L2",
                                     recency=_recency(ep.ts, now, self.cfg.recency_tau_hours),
                                     relevance=0.7 if ep.kind != "turn" else 0.4,
                                     pin=0.0),
                    )
                )
            # Semantic chunks: first few at L2, remainder at L3 (ambient warm-up)
            for idx, chunk in enumerate(inp.recall.semantic):
                rel = chunk.score if chunk.score is not None else 0.5
                lvl: Level = "L2" if idx < 4 else "L3"
                text = f"[semantic] {chunk.text}"
                items.append(
                    ContextItem(
                        item_id=new_id(f"{lvl.lower()}s"),
                        level=lvl,
                        source="semantic",
                        source_id=chunk.source_id,
                        text=text,
                        tokens=count_tokens(text, inp.model),
                        score=_score(w, level=lvl,
                                     recency=_recency(chunk.ts, now, self.cfg.recency_tau_hours),
                                     relevance=rel, pin=0.0),
                    )
                )

        # L3: older buffer (anything before last K)
        older = list(inp.buffer)[:-recent_n] if recent_n < len(inp.buffer) else []
        for turn in older:
            if turn.role == "system":
                continue
            text = f"(older) {turn.role}: {turn.content.strip()[:140]}"
            items.append(
                ContextItem(
                    item_id=f"l3_{turn.turn_id}",
                    level="L3",
                    source="buffer",
                    source_id=turn.turn_id,
                    text=text,
                    tokens=count_tokens(text, inp.model),
                    score=_score(w, level="L3",
                                 recency=_recency(turn.ts, now, self.cfg.recency_tau_hours),
                                 relevance=0.2, pin=0.0),
                )
            )

        return items

    # ---------- transforms ----------

    def _drop_level(self, items: list[ContextItem], level: Level) -> list[ContextItem]:
        return [it for it in items if it.level != level]

    def _trim_l2(self, items: list[ContextItem], budget: int) -> list[ContextItem]:
        l2 = [it for it in items if it.level == "L2"]
        others = [it for it in items if it.level != "L2"]
        l2_sorted = sorted(l2, key=lambda it: -(it.score.value if it.score else 0.0))
        current = sum(it.tokens for it in others)
        kept: list[ContextItem] = []
        for it in l2_sorted:
            if current + it.tokens > budget:
                break
            kept.append(it)
            current += it.tokens
        return others + kept

    def _summarize_l1(self, items: list[ContextItem], model: str) -> list[ContextItem]:
        l1 = [it for it in items if it.level == "L1"]
        others = [it for it in items if it.level != "L1"]
        if len(l1) < 2:
            return items
        l1_sorted = sorted(l1, key=lambda it: it.item_id)
        # condense oldest pair
        a, b = l1_sorted[0], l1_sorted[1]
        summary_text = self.summarizer.condense_pair(a.text, b.text)
        merged = ContextItem(
            item_id=f"l1_sum_{a.item_id}",
            level="L1",
            source="buffer",
            source_id=f"{a.source_id}+{b.source_id}",
            text=summary_text,
            tokens=count_tokens(summary_text, model),
            score=a.score,
            summarized=True,
        )
        remaining = l1_sorted[2:]
        return others + [merged] + remaining

    def _compress_l2(self, items: list[ContextItem]) -> list[ContextItem]:
        l2 = [it for it in items if it.level == "L2"]
        if not l2:
            return items
        others = [it for it in items if it.level != "L2"]
        compressed = self.summarizer.compress_items(l2)
        merged = ContextItem(
            item_id="l2_compressed",
            level="L2",
            source="semantic",
            source_id="compressed",
            text="[L2 compressed]\n" + compressed,
            tokens=count_tokens(compressed, "gpt-4o-mini"),
            score=None,
            summarized=True,
        )
        return others + [merged]

    # ---------- finalize ----------

    def _finalize(self, items: list[ContextItem], budget: int) -> ContextPack:
        # group by level, order so L0 → L1 → L2 → L3
        by_level: dict[str, list[ContextItem]] = {"L0": [], "L1": [], "L2": [], "L3": []}
        for it in items:
            by_level[it.level].append(it)
        ordered: list[ContextItem] = (
            by_level["L0"] + by_level["L1"] + by_level["L2"] + by_level["L3"]
        )
        tokens_per_level = {lv: sum(it.tokens for it in by_level[lv]) for lv in by_level}
        total = sum(tokens_per_level.values())
        return ContextPack(
            items=ordered,
            tokens_per_level=tokens_per_level,
            total_tokens=total,
            budget_tokens=budget,
            headroom_tokens=self.cfg.response_headroom_tokens,
            dropped_ids=[],
            summarized_ids=[it.item_id for it in ordered if it.summarized],
        )


# ---------- scoring helpers ----------

def _score(
    weights: dict[str, float],
    level: Level,
    recency: float,
    relevance: float,
    pin: float,
) -> PriorityScore:
    level_weight = {"L0": 1.0, "L1": 0.75, "L2": 0.5, "L3": 0.2}[level]
    value = (
        weights.get("level", 1.0) * level_weight
        + weights.get("recency", 0.3) * recency
        + weights.get("relevance", 0.7) * relevance
        + weights.get("pin", 0.5) * pin
    )
    return PriorityScore(
        value=round(value, 4),
        level_weight=level_weight,
        recency=round(recency, 4),
        relevance=round(relevance, 4),
        pin=pin,
    )


def _recency(ts: datetime, now: datetime, tau_hours: float) -> float:
    delta = max(0.0, (now - ts).total_seconds() / 3600.0)
    return math.exp(-delta / max(tau_hours, 0.1))
