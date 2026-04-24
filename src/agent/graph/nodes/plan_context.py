from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Optional

from agent.graph.state import AgentContext, AgentState
from agent.schemas.core import Turn
from agent.schemas.routing import RecallResult
from agent.services.context_manager import AssembleInputs, ContextBudgetError


SYSTEM_PROMPT = (
    "You are a helpful assistant with persistent memory of the user. "
    "When recalled preferences, facts or episodes are included below, use them naturally. "
    "Avoid asking the user for information you already have. "
    "Respect their stated likes and dislikes."
)


def _pinned_profile(recall: Optional[RecallResult]) -> Optional[str]:
    if not recall:
        return None
    pref_lines: list[str] = []
    for p in recall.preferences:
        pref_lines.append(f"- {p.key} = {p.value}")
    if not pref_lines:
        return None
    return "User profile (active preferences):\n" + "\n".join(pref_lines)


def make_plan_context(ctx: AgentContext) -> Callable[[AgentState], dict]:
    def plan_context(state: AgentState) -> dict:
        t0 = time.perf_counter()
        flags = state.get("flags", {}) or {}
        buffer_dicts = state.get("buffer", []) or []
        buffer: list[Turn] = []
        for d in buffer_dicts:
            try:
                buffer.append(Turn.model_validate(d))
            except Exception:
                continue

        recall_dict = state.get("recall") if flags.get("memory_enabled", True) else None
        recall = None
        if recall_dict:
            try:
                recall = RecallResult.model_validate(recall_dict)
            except Exception:
                recall = None

        pinned = _pinned_profile(recall) if flags.get("memory_enabled", True) else None

        # Exclude the current (just-ingested) user turn from the buffer passed to L1
        # — context_manager adds the current user message as L0.
        dialog = [t for t in buffer if t.turn_id != state["turn_id"]]

        inputs = AssembleInputs(
            system_prompt=SYSTEM_PROMPT,
            user_message=state["user_message"],
            buffer=dialog,
            recall=recall,
            pinned_profile=pinned,
            model=ctx.settings.runtime.model,
            now=datetime.utcnow(),
        )
        errors = list(state.get("errors", []) or [])
        try:
            pack = ctx.context_manager.assemble(inputs)
        except ContextBudgetError as exc:
            errors.append({"node": "plan_context", "kind": "budget", "message": str(exc)})
            from agent.schemas.context import ContextPack, ContextItem
            fallback_text = f"User: {state['user_message']}"
            pack = ContextPack(
                items=[ContextItem(
                    item_id="l0_fallback", level="L0", source="system",
                    source_id="fallback", text=fallback_text,
                    tokens=len(fallback_text) // 4,
                )],
                tokens_per_level={"L0": len(fallback_text) // 4},
                total_tokens=len(fallback_text) // 4,
                budget_tokens=ctx.settings.context.budget_tokens,
                headroom_tokens=ctx.settings.context.response_headroom_tokens,
                degraded=True,
            )

        latency = state.get("latency_ms", {}) or {}
        latency["plan"] = round((time.perf_counter() - t0) * 1000.0, 3)
        return {
            "context_pack": pack.model_dump(mode="json"),
            "errors": errors,
            "latency_ms": latency,
        }

    return plan_context
