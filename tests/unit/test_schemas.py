from datetime import datetime

import pytest
from pydantic import ValidationError

from agent.schemas.benchmark import Scenario
from agent.schemas.memory import Episode, Preference


def test_preference_defaults():
    p = Preference(user_id="u", key="language.liked", value="python")
    assert p.confidence == 1.0
    assert p.schema_version == 1


def test_episode_requires_kind_literal():
    with pytest.raises(ValidationError):
        Episode(episode_id="e", user_id="u", session_id="s", kind="unknown_kind",  # type: ignore
                summary="x")


def test_scenario_load_from_dict():
    data = {
        "id": "x", "title": "t", "category": "c",
        "sessions": [[{"turn_idx": 0, "user": "hi"}]],
    }
    s = Scenario.model_validate(data)
    assert s.id == "x"
    assert len(s.sessions) == 1
    assert s.sessions[0][0].user == "hi"
