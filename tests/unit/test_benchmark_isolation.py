from datetime import datetime
from pathlib import Path
from uuid import uuid4

from agent.config import load_settings
from agent.memory.episodic import EpisodicMemory
from agent.schemas.benchmark import Scenario, ScenarioTurn
from agent.schemas.memory import Episode
from benchmark.runner import _run_scenario


def test_benchmark_scenario_starts_with_clean_episodic_memory():
    base = Path("outputs") / "test_benchmark_isolation" / uuid4().hex
    settings = load_settings()
    settings.runtime.mode = "mock"
    settings.embedding.mode = "hash"
    settings.use_fake_redis = True
    settings.use_ephemeral_chroma = True
    settings.user.default_user_id = "isolation_user"
    settings.memory.episodic.log_dir = str(base / "episodic")
    settings.memory.semantic.persist_dir = str(base / "chroma")

    stale = EpisodicMemory(settings.memory.episodic.log_dir)
    stale.write(Episode(
        episode_id="stale_confusion",
        user_id=settings.user.default_user_id,
        session_id="old_session",
        kind="confusion",
        summary="User showed confusion: async/await was confusing.",
        context_excerpt="old run",
        tags=["async-await"],
        ts=datetime.utcnow(),
    ))

    scenario = Scenario(
        id="isolation_check",
        title="Isolation check",
        category="experience",
        sessions=[[
            ScenarioTurn(
                turn_idx=0,
                user="Can you explain async/await again?",
                expected_signals=[],
            )
        ]],
    )

    result = _run_scenario(
        scenario=scenario,
        settings=settings,
        run_id="isolation_run",
        memory_enabled=True,
        turn_log_path=base / "turns.jsonl",
    )

    assert result.turn_records[0].recall_counts["episodes"] == 0
