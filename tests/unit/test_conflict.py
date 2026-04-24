from datetime import datetime, timedelta

from agent.memory.conflict import ConflictResolver
from agent.schemas.memory import Preference


def test_merge_same_value_keeps_max_confidence():
    r = ConflictResolver()
    a = Preference(user_id="u", key="language.liked", value="python",
                   confidence=0.8, updated_at=datetime.utcnow() - timedelta(days=1))
    b = Preference(user_id="u", key="language.liked", value="python",
                   confidence=0.95, updated_at=datetime.utcnow())
    merged = r.merge_preference(a, b)
    assert merged.confidence >= 0.95


def test_newer_wins_on_conflict():
    r = ConflictResolver()
    a = Preference(user_id="u", key="language.liked", value="python",
                   confidence=0.8, updated_at=datetime.utcnow() - timedelta(days=3))
    b = Preference(user_id="u", key="language.liked", value="rust",
                   confidence=0.85, updated_at=datetime.utcnow())
    merged = r.merge_preference(a, b)
    assert merged.value == "rust"


def test_much_lower_confidence_even_if_newer_loses():
    r = ConflictResolver()
    a = Preference(user_id="u", key="language.liked", value="python",
                   confidence=0.9, updated_at=datetime.utcnow() - timedelta(days=3))
    b = Preference(user_id="u", key="language.liked", value="rust",
                   confidence=0.5, updated_at=datetime.utcnow())
    merged = r.merge_preference(a, b)
    assert merged.value == "python"
