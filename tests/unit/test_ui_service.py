from pathlib import Path
from uuid import uuid4

from agent.config import load_settings
from agent.ui.app import AgentUiService


def _service() -> AgentUiService:
    base = Path("outputs") / "test_ui" / uuid4().hex
    settings = load_settings()
    settings.runtime.mode = "mock"
    settings.embedding.mode = "hash"
    settings.use_fake_redis = True
    settings.use_ephemeral_chroma = True
    settings.memory.episodic.log_dir = str(base / "episodic")
    settings.memory.semantic.persist_dir = str(base / "chroma")
    return AgentUiService(settings=settings)


def test_ui_service_ask_returns_observability_payload():
    svc = _service()
    result = svc.ask(
        message="Tôi thích Python, không thích Java.",
        user_id="ui_user",
        session_id="s1",
        memory_enabled=True,
    )

    assert result["assistant_response"]
    assert result["router"]["top_intent"] == "preference_capture"
    assert result["persisted"]["pref_writes"] >= 1
    assert "prompt_tokens" in result["usage"]


def test_ui_service_compare_runs_memory_and_no_memory_variants():
    svc = _service()
    user_id = "ui_compare_user"
    svc.ask("Tôi thích Python, không thích Java.", user_id, "seed", True)

    result = svc.compare(
        message="Which language should I use for a simple script?",
        user_id=user_id,
        session_id="compare",
    )

    assert set(result) == {"with_memory", "without_memory", "delta"}
    assert result["with_memory"]["memory_enabled"] is True
    assert result["without_memory"]["memory_enabled"] is False
    assert result["with_memory"]["recall_counts"]["preferences"] >= 1


def test_ui_service_full_demo_covers_required_sessions():
    svc = _service()
    result = svc.run_full_demo(user_id="ui_demo_user")

    labels = [step["label"] for step in result["steps"]]
    assert "Session 1: preference write" in labels
    assert "Session 2: cross-session recall" in labels
    assert "Session 3: confusion episode" in labels
    assert result["comparisons"]["language"]["with_memory"]["memory_enabled"] is True
