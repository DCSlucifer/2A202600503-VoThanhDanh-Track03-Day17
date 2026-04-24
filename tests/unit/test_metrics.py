from agent.schemas.benchmark import ScenarioTurn, TurnRecord
from benchmark.metrics import (
    context_utilization,
    false_amnesia,
    memory_hit_rate,
    response_relevance,
    token_efficiency,
    user_satisfaction_proxy,
)


def _turn(**kwargs) -> TurnRecord:
    base = dict(
        run_id="r", scenario_id="s", session_idx=0, turn_idx=0,
        user_id="u", session_id="sess", memory_enabled=True,
        user_message="hi", assistant_response="hello",
        recall_counts={}, context_pack_stats={}, usage={},
        latency_ms={}, persisted={}, errors=[], metrics={},
    )
    base.update(kwargs)
    return TurnRecord(**base)


def test_relevance_full_coverage_no_negatives():
    tr = _turn(assistant_response="Python is the answer")
    st = ScenarioTurn(turn_idx=0, user="x", expected_signals=["Python"])
    assert response_relevance(tr, st) == 1.0


def test_relevance_penalises_negatives():
    tr = _turn(assistant_response="Use Python and Java")
    st = ScenarioTurn(turn_idx=0, user="x",
                      expected_signals=["Python"], negative_signals=["Java"])
    assert response_relevance(tr, st) == 0.0


def test_context_utilization_fraction_from_l2():
    tr = _turn(context_pack_stats={
        "tokens_per_level": {"L0": 100, "L1": 100, "L2": 200, "L3": 100},
        "total_tokens": 500,
    })
    st = ScenarioTurn(turn_idx=0, user="x")
    assert abs(context_utilization(tr, st) - 0.4) < 1e-6


def test_token_efficiency_zero_when_no_usage():
    tr = _turn(assistant_response="Python", usage={"prompt_tokens": 0})
    st = ScenarioTurn(turn_idx=0, user="x", expected_signals=["Python"])
    assert token_efficiency(tr, st) == 0.0


def test_memory_hit_rate_requires_retrieval_and_match():
    tr = _turn(assistant_response="Python",
               recall_counts={"preferences": 1})
    st = ScenarioTurn(turn_idx=0, user="x", expected_signals=["Python"])
    assert memory_hit_rate(tr, st) == 1.0
    tr2 = _turn(assistant_response="Python", recall_counts={})
    assert memory_hit_rate(tr2, st) == 0.0


def test_false_amnesia_triggers_on_dont_know():
    tr = _turn(assistant_response="I don't know what you prefer")
    st = ScenarioTurn(turn_idx=0, user="x", expected_signals=["Python"])
    assert false_amnesia(tr, st) == 1.0


def test_satisfaction_combines_parts():
    tr = _turn(assistant_response="Using Python, avoiding java-based stuff")
    st = ScenarioTurn(turn_idx=0, user="x",
                      expected_signals=["Python"], negative_signals=["avoid"])
    # violating avoid triggers a violation; relevance: 1.0 - 1.0 = 0.0
    sat = user_satisfaction_proxy(tr, st)
    assert 0.0 <= sat <= 1.0
