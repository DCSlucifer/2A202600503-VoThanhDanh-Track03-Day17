"""Smoke test: one full turn through the graph with the mock runtime."""
import uuid

from agent.config import reset_settings
from agent.graph import build_context, build_graph


def test_single_turn_smoke(tmp_outputs_dir):
    reset_settings()
    ctx = build_context()
    graph = build_graph(ctx)
    state = {
        "user_id": "u_smoke",
        "session_id": f"sess_{uuid.uuid4().hex[:6]}",
        "turn_id": "t0",
        "user_message": "Hello!",
        "flags": {"memory_enabled": True, "run_id": "run_test",
                  "scenario_id": "smoke", "turn_idx": 0, "session_idx": 0},
        "errors": [],
        "latency_ms": {},
    }
    out = graph.invoke(state)
    assert "assistant_response" in out
    assert isinstance(out["assistant_response"], str)
    assert out["router_trace"] is not None
    assert out["context_pack"] is not None
    assert "total_tokens" in out["context_pack"]


def test_memory_disabled_skips_route_and_recall(tmp_outputs_dir):
    reset_settings()
    ctx = build_context()
    graph = build_graph(ctx)
    state = {
        "user_id": "u_nomem",
        "session_id": "sess_nomem",
        "turn_id": "t0",
        "user_message": "Which language?",
        "flags": {"memory_enabled": False, "run_id": "run_test",
                  "scenario_id": "smoke", "turn_idx": 0, "session_idx": 0},
        "errors": [],
        "latency_ms": {},
    }
    out = graph.invoke(state)
    recall = out.get("recall") or {}
    # with memory disabled, recall content should be empty
    assert len(recall.get("preferences", []) or []) == 0
    assert len(recall.get("facts", []) or []) == 0
    assert out.get("persisted", {}).get("pref_writes", 0) == 0
