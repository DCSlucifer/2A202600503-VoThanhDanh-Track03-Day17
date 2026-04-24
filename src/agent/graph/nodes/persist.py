from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from agent.graph.state import AgentContext, AgentState
from agent.schemas.core import Turn
from agent.utils.ids import new_id


def make_persist(ctx: AgentContext) -> Callable[[AgentState], dict]:
    def persist(state: AgentState) -> dict:
        t0 = time.perf_counter()
        errors = list(state.get("errors", []) or [])
        flags = state.get("flags", {}) or {}

        if not flags.get("memory_enabled", True):
            latency = state.get("latency_ms", {}) or {}
            latency["persist"] = round((time.perf_counter() - t0) * 1000.0, 3)
            return {
                "persisted": {
                    "pref_writes": 0,
                    "fact_writes": 0,
                    "episode_writes": 0,
                    "semantic_writes": 0,
                },
                "latency_ms": latency,
            }

        user_id = state["user_id"]
        session_id = state["session_id"]

        user_turn = Turn(
            turn_id=state["turn_id"],
            role="user",
            content=state["user_message"],
            ts=datetime.utcnow(),
            session_id=session_id,
        )
        assistant_turn = Turn(
            turn_id=f"{state['turn_id']}_a",
            role="assistant",
            content=state.get("assistant_response", "") or "",
            ts=datetime.utcnow(),
            session_id=session_id,
        )

        pref_writes = 0
        fact_writes = 0
        semantic_writes = 0

        # --- preferences + profile facts ---
        try:
            if ctx.settings.memory.extraction_mode == "llm":
                extraction = ctx.llm_extractor.extract(user_turn, user_id=user_id)
                prefs = extraction.preferences
                facts = extraction.facts
                for err in extraction.errors:
                    errors.append({"node": "persist", **err})
            else:
                prefs = ctx.preference_extractor.extract(user_turn, user_id=user_id)
                facts = ctx.fact_extractor.extract(user_turn, user_id=user_id)

            for pref in prefs:
                ctx.redis.write(pref)
                pref_writes += 1
                chunk = ctx.semantic_writer.from_preference(pref)
                ctx.semantic.write(chunk)
                semantic_writes += 1

            for fact in facts:
                ctx.redis.write(fact)
                fact_writes += 1
                chunk = ctx.semantic_writer.from_fact(fact)
                ctx.semantic.write(chunk)
                semantic_writes += 1
        except Exception as exc:
            errors.append({"node": "persist", "kind": "extract", "message": str(exc)})

        # --- episodes ---
        episode_writes = 0
        try:
            episode = ctx.episode_writer.build(
                user_turn=user_turn,
                assistant_turn=assistant_turn,
                user_id=user_id,
                session_id=session_id,
            )
            ctx.episodic.write(episode)
            episode_writes += 1
            sem = ctx.semantic_writer.from_episode(episode)
            if sem is not None:
                ctx.semantic.write(sem)
                semantic_writes += 1
        except Exception as exc:
            errors.append({"node": "persist", "kind": "episode", "message": str(exc)})

        latency = state.get("latency_ms", {}) or {}
        latency["persist"] = round((time.perf_counter() - t0) * 1000.0, 3)
        return {
            "persisted": {
                "pref_writes": pref_writes,
                "fact_writes": fact_writes,
                "episode_writes": episode_writes,
                "semantic_writes": semantic_writes,
            },
            "errors": errors,
            "latency_ms": latency,
        }

    return persist
