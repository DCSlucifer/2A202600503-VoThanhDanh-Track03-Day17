from datetime import datetime, timedelta

from agent.config import ContextConfig
from agent.schemas.core import Turn
from agent.schemas.memory import Episode, Preference, SemanticChunk
from agent.schemas.routing import RecallResult, RouterDecision
from agent.services.context_manager import (
    AssembleInputs,
    ContextBudgetError,
    ContextManager,
)
from agent.services.summarizer import Summarizer


def _mk_ctx(budget: int = 2000) -> ContextManager:
    cfg = ContextConfig(budget_tokens=budget, response_headroom_tokens=200)
    return ContextManager(cfg, Summarizer())


def _recall_with_prefs(user_id: str = "u", n_semantic: int = 0) -> RecallResult:
    return RecallResult(
        preferences=[
            Preference(user_id=user_id, key="language.liked", value="python", confidence=0.9,
                       updated_at=datetime.utcnow()),
        ],
        semantic=[SemanticChunk(chunk_id=f"s{i}", source_id=f"s{i}", source_kind="fact",
                                text=f"fact number {i} is interesting " * 5,
                                ts=datetime.utcnow())
                  for i in range(n_semantic)],
        decision=RouterDecision(input="x", intents=[], backends=["buffer"]),
    )


def test_assemble_respects_budget_under_pressure():
    cm = _mk_ctx(budget=400)  # effective budget = 200 after headroom
    buffer = [
        Turn(turn_id=f"t{i}", role="user", content=("long chunk " * 60),
             ts=datetime.utcnow() - timedelta(minutes=i), session_id="s1")
        for i in range(8)
    ]
    pack = cm.assemble(AssembleInputs(
        system_prompt="system prompt",
        user_message="current msg",
        buffer=buffer,
        recall=_recall_with_prefs(n_semantic=6),
    ))
    assert pack.total_tokens <= pack.budget_tokens + 1


def test_l0_never_shrinks():
    cm = _mk_ctx(budget=10_000)
    pack = cm.assemble(AssembleInputs(
        system_prompt="system prompt body",
        user_message="hi",
        buffer=[],
        recall=None,
        pinned_profile="User prefers Python.",
    ))
    l0_items = pack.level_items("L0")
    # system + profile + current user msg
    assert len(l0_items) == 3


def test_degraded_pack_when_l0_exceeds_budget():
    cm = _mk_ctx(budget=50)  # absurdly low; response headroom larger than budget
    cm.cfg.response_headroom_tokens = 0
    try:
        cm.assemble(AssembleInputs(
            system_prompt="This is a relatively long system prompt " * 50,
            user_message="any",
            buffer=[],
            recall=None,
        ))
    except ContextBudgetError:
        return  # acceptable outcome
    raise AssertionError("expected ContextBudgetError when L0 alone blows the budget")


def test_tokens_per_level_sum_matches_total():
    cm = _mk_ctx(budget=5000)
    pack = cm.assemble(AssembleInputs(
        system_prompt="sys",
        user_message="hi",
        buffer=[Turn(turn_id="t1", role="user", content="hello",
                     ts=datetime.utcnow(), session_id="s1")],
        recall=_recall_with_prefs(),
    ))
    assert sum(pack.tokens_per_level.values()) == pack.total_tokens


def test_confusion_episode_adds_adaptation_guidance():
    cm = _mk_ctx(budget=5000)
    episode = Episode(
        episode_id="ep_confusion_1",
        user_id="u",
        session_id="s1",
        kind="confusion",
        summary="User showed confusion: async/await in Python was confusing.",
        context_excerpt="",
        tags=["async-await"],
        ts=datetime.utcnow(),
    )
    pack = cm.assemble(AssembleInputs(
        system_prompt="sys",
        user_message="Can you explain async/await again?",
        buffer=[],
        recall=RecallResult(
            episodes=[episode],
            decision=RouterDecision(
                input="Can you explain async/await again?",
                intents=[],
                backends=["episodic"],
            ),
        ),
    ))
    prompt = pack.render_prompt().lower()
    assert "simple terms" in prompt
    assert "step by step" in prompt
