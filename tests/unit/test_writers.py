from datetime import datetime

from agent.memory.writers import (
    EpisodeWriter,
    FactExtractor,
    PreferenceExtractor,
    SemanticWriter,
    classify_episode,
)
from agent.schemas.core import Turn


def _mk_turn(content: str, role: str = "user") -> Turn:
    return Turn(turn_id="t1", role=role, content=content, ts=datetime.utcnow(),
                session_id="s1")


def test_pref_extract_vn_positive():
    ex = PreferenceExtractor()
    prefs = ex.extract(_mk_turn("Tôi thích Python"), user_id="u")
    assert any(p.key == "language.liked" and p.value == "python" for p in prefs)


def test_pref_extract_vn_negative():
    ex = PreferenceExtractor()
    prefs = ex.extract(_mk_turn("Tôi không thích Java"), user_id="u")
    assert any(p.key == "language.disliked" and p.value == "java" for p in prefs)


def test_pref_extract_combined():
    ex = PreferenceExtractor()
    prefs = ex.extract(_mk_turn("Tôi thích Python, không thích Java"), user_id="u")
    keys = {(p.key, p.value) for p in prefs}
    assert ("language.liked", "python") in keys
    assert ("language.disliked", "java") in keys


def test_pref_extract_en_positive():
    ex = PreferenceExtractor()
    prefs = ex.extract(_mk_turn("I really love Rust"), user_id="u")
    assert any(p.value == "rust" for p in prefs)


def test_pref_extract_non_language_token_ignored():
    ex = PreferenceExtractor()
    prefs = ex.extract(_mk_turn("I like pizza"), user_id="u")
    assert prefs == []


def test_fact_extract_vn_allergy():
    ex = FactExtractor()
    facts = ex.extract(_mk_turn("Tôi dị ứng sữa bò."), user_id="u")
    assert len(facts) == 1
    fact = facts[0]
    assert fact.fact_id == "profile.allergy"
    assert fact.predicate == "allergy"
    assert fact.object == "sữa bò"


def test_fact_extract_vn_allergy_correction():
    ex = FactExtractor()
    facts = ex.extract(
        _mk_turn("À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò."),
        user_id="u",
    )
    assert len(facts) == 1
    fact = facts[0]
    assert fact.fact_id == "profile.allergy"
    assert fact.object == "đậu nành"
    assert "sữa bò" not in fact.object


def test_fact_extract_technical_stack():
    ex = FactExtractor()
    facts = ex.extract(_mk_turn("I'm using Postgres 15 for this project."), user_id="u")
    assert len(facts) == 1
    fact = facts[0]
    assert fact.fact_id == "profile.stack"
    assert fact.predicate == "uses"
    assert fact.object == "Postgres 15 for this project"


def test_episode_classification():
    assert classify_episode("I'm confused about async/await") == "confusion"
    assert classify_episode("à ra hiểu rồi") == "breakthrough"
    assert classify_episode("got a traceback error") == "error_recovery"
    assert classify_episode("hello how are you") == "turn"


def test_episode_writer_tags_async_await():
    w = EpisodeWriter()
    u = _mk_turn("I'm confused about async/await")
    a = _mk_turn("Let me explain...", role="assistant")
    ep = w.build(user_turn=u, assistant_turn=a, user_id="u", session_id="s1")
    assert ep.kind == "confusion"
    assert "async-await" in ep.tags


def test_semantic_writer_from_episode_skips_plain_turn():
    sw = SemanticWriter()
    w = EpisodeWriter()
    u = _mk_turn("hello", role="user")
    a = _mk_turn("hi", role="assistant")
    ep = w.build(u, a, user_id="u", session_id="s1")
    assert sw.from_episode(ep) is None
