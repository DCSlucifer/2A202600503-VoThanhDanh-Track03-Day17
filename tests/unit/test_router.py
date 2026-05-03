from agent.config import RouterConfig
from agent.services.router import MemoryRouter


def _router() -> MemoryRouter:
    return MemoryRouter(RouterConfig())


def test_preference_capture_vn_positive():
    r = _router()
    d = r.route("Tôi thích Python")
    assert d.intents[0].name == "preference_capture"
    assert "buffer" in d.backends


def test_preference_capture_en_positive():
    r = _router()
    d = r.route("I really like Rust")
    assert d.intents[0].name == "preference_capture"


def test_preference_recall_selects_redis_pref():
    r = _router()
    d = r.route("Which language should I use for this?")
    assert d.intents[0].name == "preference_recall"
    assert "redis_pref" in d.backends
    assert "semantic" in d.backends


def test_factual_recall_selects_redis_fact():
    r = _router()
    d = r.route("Remind me what my role is?")
    assert d.intents[0].name == "factual_recall"
    assert "redis_fact" in d.backends


def test_allergy_question_selects_redis_fact():
    r = _router()
    d = r.route("Tôi dị ứng gì?")
    assert d.intents[0].name == "factual_recall"
    assert "redis_fact" in d.backends


def test_allergy_statement_is_fact_capture_without_redis_read():
    r = _router()
    d = r.route("Tôi dị ứng sữa bò.")
    assert d.intents[0].name == "fact_capture"
    assert "redis_fact" not in d.backends


def test_experience_recall_selects_episodic():
    r = _router()
    d = r.route("Have I seen this async/await pattern before?")
    assert d.intents[0].name == "experience_recall"
    assert "episodic" in d.backends


def test_task_default_uses_semantic_warmup_with_fallback_flag():
    """Per plan §4.3, low-confidence task turns still pull a Chroma warm-up so
    cross-session preferences can surface even when not asked. Precision is the
    job of the LLM + negative-signal benchmark, not the router."""
    r = _router()
    d = r.route("What's the boiling point of water?")
    assert "buffer" in d.backends
    assert "semantic" in d.backends
    assert d.fallback_used is True
    # but never long-term redis when not explicitly asked
    assert "redis_pref" not in d.backends
    assert "redis_fact" not in d.backends


def test_max_backends_cap():
    r = _router()
    d = r.route("Remind me what I prefer and what tripped me up before")
    assert len(d.backends) <= RouterConfig().max_backends_per_turn
