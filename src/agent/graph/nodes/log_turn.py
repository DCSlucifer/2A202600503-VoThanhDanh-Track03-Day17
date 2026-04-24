from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from agent.graph.state import AgentContext, AgentState


def make_log_turn(ctx: AgentContext) -> Callable[[AgentState], dict]:
    def log_turn(state: AgentState) -> dict:
        flags = state.get("flags", {}) or {}
        context_stats = {}
        pack = state.get("context_pack") or {}
        if pack:
            context_stats = {
                "tokens_per_level": pack.get("tokens_per_level", {}),
                "total_tokens": pack.get("total_tokens", 0),
                "budget_tokens": pack.get("budget_tokens", 0),
                "headroom_tokens": pack.get("headroom_tokens", 0),
                "summarized_ids": pack.get("summarized_ids", []),
                "degraded": pack.get("degraded", False),
            }

        recall = state.get("recall") or {}
        recall_counts = {
            "preferences": len(recall.get("preferences", []) or []),
            "facts": len(recall.get("facts", []) or []),
            "episodes": len(recall.get("episodes", []) or []),
            "semantic": len(recall.get("semantic", []) or []),
        }

        llm_resp = state.get("llm_response") or {}
        record = {
            "run_id": flags.get("run_id", "unknown"),
            "scenario_id": flags.get("scenario_id", "interactive"),
            "session_idx": flags.get("session_idx", 0),
            "turn_idx": flags.get("turn_idx", 0),
            "user_id": state.get("user_id"),
            "session_id": state.get("session_id"),
            "memory_enabled": flags.get("memory_enabled", True),
            "user_message": state.get("user_message"),
            "assistant_response": state.get("assistant_response", ""),
            "router_trace": state.get("router_trace"),
            "recall_counts": recall_counts,
            "context_pack_stats": context_stats,
            "usage": llm_resp.get("usage", {"prompt_tokens": 0, "completion_tokens": 0}),
            "latency_ms": state.get("latency_ms", {}),
            "persisted": state.get("persisted", {}),
            "errors": state.get("errors", []),
            "ts": datetime.utcnow().isoformat(),
        }

        if ctx.turn_logger is not None:
            try:
                ctx.turn_logger.write(record)
            except Exception:
                pass

        return {"log_written": True}

    return log_turn
