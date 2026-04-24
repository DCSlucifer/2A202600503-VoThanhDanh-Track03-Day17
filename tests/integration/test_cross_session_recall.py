"""Demo #1 + #2: preference captured in session A is recalled in session B."""
import uuid

from agent.config import reset_settings
from agent.graph import build_context, build_graph


def _invoke(graph, state):
    return graph.invoke(state)


def test_preference_persists_across_sessions(tmp_outputs_dir):
    reset_settings()
    ctx = build_context()
    graph = build_graph(ctx)

    user_id = "u_x"
    # Session A: user declares preference
    session_a = f"sA_{uuid.uuid4().hex[:6]}"
    out_a = _invoke(graph, {
        "user_id": user_id,
        "session_id": session_a,
        "turn_id": "t0",
        "user_message": "Tôi thích Python, không thích Java.",
        "flags": {"memory_enabled": True, "run_id": "run_test",
                  "scenario_id": "cross_sess", "turn_idx": 0, "session_idx": 0},
        "errors": [],
        "latency_ms": {},
    })
    assert (out_a.get("persisted") or {}).get("pref_writes", 0) >= 1

    # Verify Redis has the preference
    prefs = ctx.redis.read(user_id=user_id, kind="preference")
    kinds = {(p.key, p.value) for p in prefs}
    assert ("language.liked", "python") in kinds
    assert ("language.disliked", "java") in kinds

    # Session B: new session, different id. Agent should recall preference proactively.
    session_b = f"sB_{uuid.uuid4().hex[:6]}"
    out_b = _invoke(graph, {
        "user_id": user_id,
        "session_id": session_b,
        "turn_id": "t0",
        "user_message": "Which language should I use for a simple script?",
        "flags": {"memory_enabled": True, "run_id": "run_test",
                  "scenario_id": "cross_sess", "turn_idx": 0, "session_idx": 1},
        "errors": [],
        "latency_ms": {},
    })
    resp = out_b["assistant_response"]
    recall = out_b.get("recall") or {}
    assert len(recall.get("preferences", [])) >= 1
    assert "Python" in resp
    assert "Java" not in resp.replace("avoid Java", "")  # mentioned only in an avoidance phrase


def test_confusion_episode_softens_later_explanation(tmp_outputs_dir):
    reset_settings()
    ctx = build_context()
    graph = build_graph(ctx)
    user_id = "u_y"

    session_a = f"sAA_{uuid.uuid4().hex[:6]}"
    _invoke(graph, {
        "user_id": user_id,
        "session_id": session_a,
        "turn_id": "t0",
        "user_message": "I'm confused about async/await.",
        "flags": {"memory_enabled": True, "run_id": "run_test",
                  "scenario_id": "episodic", "turn_idx": 0, "session_idx": 0},
        "errors": [],
        "latency_ms": {},
    })

    session_b = f"sBB_{uuid.uuid4().hex[:6]}"
    out_b = _invoke(graph, {
        "user_id": user_id,
        "session_id": session_b,
        "turn_id": "t0",
        "user_message": "Can you explain async/await again?",
        "flags": {"memory_enabled": True, "run_id": "run_test",
                  "scenario_id": "episodic", "turn_idx": 0, "session_idx": 1},
        "errors": [],
        "latency_ms": {},
    })
    resp = out_b["assistant_response"].lower()
    # mock adds simpler-tone phrasing when episode:confusion appears
    simplifiers = ["tricky before", "step by step", "simple terms",
                   "beginner-friendly", "break this down"]
    assert any(s in resp for s in simplifiers)
