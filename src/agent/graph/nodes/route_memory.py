from __future__ import annotations

import time
from typing import Callable

from agent.graph.state import AgentContext, AgentState


def make_route_memory(ctx: AgentContext) -> Callable[[AgentState], dict]:
    def route_memory(state: AgentState) -> dict:
        t0 = time.perf_counter()
        flags = state.get("flags", {}) or {}
        if not flags.get("memory_enabled", True):
            # fast path — still emit a trace so logs are uniform
            trace = {
                "input": state["user_message"],
                "intents": [],
                "backends": ["buffer"],
                "fallback_used": False,
                "elapsed_ms": 0.0,
                "matched_rules": [],
            }
            latency = state.get("latency_ms", {}) or {}
            latency["route"] = round((time.perf_counter() - t0) * 1000.0, 3)
            return {"router_trace": trace, "latency_ms": latency}
        decision = ctx.router.route(state["user_message"])
        latency = state.get("latency_ms", {}) or {}
        latency["route"] = round((time.perf_counter() - t0) * 1000.0, 3)
        return {"router_trace": decision.model_dump(mode="json"), "latency_ms": latency}

    return route_memory
