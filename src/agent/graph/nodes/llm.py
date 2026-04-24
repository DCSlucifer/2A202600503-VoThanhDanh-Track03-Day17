from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from agent.graph.state import AgentContext, AgentState
from agent.schemas.context import ContextPack
from agent.schemas.core import Turn


def make_llm(ctx: AgentContext) -> Callable[[AgentState], dict]:
    def llm(state: AgentState) -> dict:
        t0 = time.perf_counter()
        errors = list(state.get("errors", []) or [])
        pack_dict = state.get("context_pack") or {}
        try:
            pack = ContextPack.model_validate(pack_dict)
            prompt = pack.render_prompt()
        except Exception as exc:
            errors.append({"node": "llm", "kind": "prompt_build", "message": str(exc)})
            prompt = f"User: {state['user_message']}"

        assistant_text = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        try:
            resp = ctx.runtime.generate(
                prompt,
                temperature=ctx.settings.runtime.temperature,
                max_tokens=ctx.settings.runtime.max_tokens,
                seed=ctx.settings.runtime.seed,
            )
            assistant_text = resp.content
            usage = {
                "prompt_tokens": resp.prompt_tokens,
                "completion_tokens": resp.completion_tokens,
            }
        except Exception as exc:
            errors.append({"node": "llm", "kind": "generate", "message": str(exc)})

        # Append assistant turn to buffer so it shows up in next-turn L1
        assistant_turn = Turn(
            turn_id=f"{state['turn_id']}_a",
            role="assistant",
            content=assistant_text,
            ts=datetime.utcnow(),
            session_id=state["session_id"],
        )
        ctx.buffer.write(assistant_turn)

        new_buffer = [t.model_dump(mode="json") for t in ctx.buffer.read(session_id=state["session_id"])]

        latency = state.get("latency_ms", {}) or {}
        latency["llm"] = round((time.perf_counter() - t0) * 1000.0, 3)
        return {
            "assistant_response": assistant_text,
            "llm_response": {"content": assistant_text, "usage": usage, "model": ctx.runtime.model},
            "buffer": new_buffer,
            "errors": errors,
            "latency_ms": latency,
        }

    return llm
