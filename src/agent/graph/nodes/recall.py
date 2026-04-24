from __future__ import annotations

import time
from typing import Callable

from agent.graph.state import AgentContext, AgentState
from agent.schemas.routing import RecallResult, RouterDecision


def make_recall(ctx: AgentContext) -> Callable[[AgentState], dict]:
    def recall(state: AgentState) -> dict:
        t0 = time.perf_counter()
        flags = state.get("flags", {}) or {}
        trace = state.get("router_trace") or {}
        try:
            decision = RouterDecision.model_validate(trace) if trace else None
        except Exception:
            decision = None

        if not flags.get("memory_enabled", True) or decision is None:
            empty = RecallResult(decision=decision or RouterDecision(
                input=state["user_message"], intents=[], backends=["buffer"],
            ))
            latency = state.get("latency_ms", {}) or {}
            latency["recall"] = round((time.perf_counter() - t0) * 1000.0, 3)
            return {"recall": empty.model_dump(mode="json"), "latency_ms": latency}

        user_id = state["user_id"]
        query = state["user_message"]
        backends = set(decision.backends)
        errors = list(state.get("errors", []) or [])

        preferences = []
        facts = []
        episodes = []
        semantic = []

        if "redis_pref" in backends:
            try:
                preferences = ctx.redis.read(user_id=user_id, kind="preference")
            except Exception as exc:
                errors.append({"node": "recall", "kind": "redis_pref", "message": str(exc)})
                preferences = []

        if "redis_fact" in backends:
            try:
                facts = ctx.redis.read(user_id=user_id, kind="fact")
            except Exception as exc:
                errors.append({"node": "recall", "kind": "redis_fact", "message": str(exc)})
                facts = []

        if "episodic" in backends:
            try:
                episodes = ctx.episodic.search(query=query, k=5, user_id=user_id)
            except Exception as exc:
                errors.append({"node": "recall", "kind": "episodic", "message": str(exc)})
                episodes = []

        if "semantic" in backends:
            try:
                # Route-dictated kind filter
                top_intent = decision.intents[0].name if decision.intents else "task_default"
                kind_filter = {
                    "preference_recall": "preference",
                    "factual_recall": "fact",
                    "experience_recall": "episode",
                }.get(top_intent)
                semantic = ctx.semantic.search(
                    query=query, k=5, user_id=user_id, kind=kind_filter
                )
            except Exception as exc:
                errors.append({"node": "recall", "kind": "semantic", "message": str(exc)})
                semantic = []

        result = RecallResult(
            preferences=list(preferences),
            facts=list(facts),
            episodes=list(episodes),
            semantic=list(semantic),
            decision=decision,
        )
        latency = state.get("latency_ms", {}) or {}
        latency["recall"] = round((time.perf_counter() - t0) * 1000.0, 3)
        return {
            "recall": result.model_dump(mode="json"),
            "errors": errors,
            "latency_ms": latency,
        }

    return recall
