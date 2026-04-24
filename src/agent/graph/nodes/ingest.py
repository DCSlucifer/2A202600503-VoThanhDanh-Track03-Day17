from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from agent.graph.state import AgentContext, AgentState
from agent.schemas.core import Turn


def make_ingest(ctx: AgentContext) -> Callable[[AgentState], dict]:
    def ingest(state: AgentState) -> dict:
        t0 = time.perf_counter()
        turn = Turn(
            turn_id=state["turn_id"],
            role="user",
            content=state["user_message"],
            ts=datetime.utcnow(),
            session_id=state["session_id"],
        )
        ctx.buffer.write(turn)
        buf = [t.model_dump(mode="json") for t in ctx.buffer.read(session_id=state["session_id"])]
        latency = state.get("latency_ms", {}) or {}
        latency["ingest"] = round((time.perf_counter() - t0) * 1000.0, 3)
        return {"buffer": buf, "errors": state.get("errors", []) or [], "latency_ms": latency}

    return ingest
