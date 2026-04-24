from pathlib import Path

from benchmark.runner import load_scenarios


def test_benchmark_markdown_contains_privacy_reflection():
    doc = Path("BENCHMARK.md")
    assert doc.exists()
    text = doc.read_text(encoding="utf-8").lower()
    for needle in ("privacy", "pii", "deletion", "ttl", "limitation"):
        assert needle in text


def test_factual_benchmark_uses_profile_facts_not_preferences():
    scenario = load_scenarios(
        Path("benchmark/scenarios"),
        ids=["s04_fact_profile"],
    )[0]
    assert scenario.oracle_facts
    assert "profile.allergy" in scenario.oracle_facts
    assert not scenario.oracle_preferences
