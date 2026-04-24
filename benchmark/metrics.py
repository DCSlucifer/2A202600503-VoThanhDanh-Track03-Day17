"""Metric functions: pure (TurnRecord + ScenarioTurn) -> float.

Each metric is independently unit-tested. Do NOT add state here.
"""
from __future__ import annotations

from typing import Callable

from agent.schemas.benchmark import ScenarioTurn, TurnRecord
from benchmark.oracle import coverage, violation_rate


MetricFn = Callable[[TurnRecord, ScenarioTurn], float]


def response_relevance(tr: TurnRecord, st: ScenarioTurn) -> float:
    """Fraction of expected signals present minus fraction of negatives violated."""
    pos = coverage(tr.assistant_response, st.expected_signals)
    neg = violation_rate(tr.assistant_response, st.negative_signals)
    return max(0.0, pos - neg)


def context_utilization(tr: TurnRecord, st: ScenarioTurn) -> float:
    stats = tr.context_pack_stats or {}
    tpl = stats.get("tokens_per_level", {}) or {}
    total = stats.get("total_tokens", 0) or 0
    l2 = tpl.get("L2", 0) or 0
    if total <= 0:
        return 0.0
    return min(1.0, l2 / total)


def token_efficiency(tr: TurnRecord, st: ScenarioTurn) -> float:
    """Relevance per 1k prompt tokens."""
    prompt_tokens = (tr.usage or {}).get("prompt_tokens", 0) or 0
    if prompt_tokens <= 0:
        return 0.0
    rel = response_relevance(tr, st)
    return rel / prompt_tokens * 1000.0


def memory_hit_rate(tr: TurnRecord, st: ScenarioTurn) -> float:
    """1.0 if at least one memory item was both retrieved AND evidenced in response."""
    if not st.expected_signals:
        return 0.0
    counts = tr.recall_counts or {}
    if sum(counts.values()) == 0:
        return 0.0
    cov = coverage(tr.assistant_response, st.expected_signals)
    return 1.0 if cov > 0 else 0.0


def preference_honor(tr: TurnRecord, st: ScenarioTurn) -> float:
    """Alias over response_relevance focused only on negative_signals (avoid disliked)."""
    if not st.negative_signals:
        return 1.0
    return 1.0 - violation_rate(tr.assistant_response, st.negative_signals)


def false_amnesia(tr: TurnRecord, st: ScenarioTurn) -> float:
    """1.0 when the agent said 'I don't know / I don't remember' while expected signals were set."""
    markers = [
        "i don't know", "i do not know", "không biết", "không nhớ",
        "i don't remember", "i haven't been told",
    ]
    low = tr.assistant_response.lower()
    has_amnesia = any(m in low for m in markers)
    if has_amnesia and st.expected_signals:
        return 1.0
    return 0.0


def user_satisfaction_proxy(tr: TurnRecord, st: ScenarioTurn) -> float:
    rel = response_relevance(tr, st)
    pref = preference_honor(tr, st)
    amnesia = false_amnesia(tr, st)
    return round(0.6 * rel + 0.2 * pref + 0.2 * (1.0 - amnesia), 4)


ALL_METRICS: dict[str, MetricFn] = {
    "response_relevance": response_relevance,
    "context_utilization": context_utilization,
    "token_efficiency": token_efficiency,
    "memory_hit_rate": memory_hit_rate,
    "user_satisfaction_proxy": user_satisfaction_proxy,
}


def score_turn(tr: TurnRecord, st: ScenarioTurn) -> dict[str, float]:
    return {name: round(fn(tr, st), 4) for name, fn in ALL_METRICS.items()}
