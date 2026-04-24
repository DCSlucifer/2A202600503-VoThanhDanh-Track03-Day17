from datetime import datetime

from agent.schemas.core import Turn
from agent.services.extraction import LLMStructuredExtractor
from agent.services.runtime.base import LLMResponse


class StaticRuntime:
    def __init__(self, content: str):
        self.content = content

    def generate(self, prompt: str, **opts):
        return LLMResponse(
            content=self.content,
            prompt_tokens=0,
            completion_tokens=0,
            model="static",
        )


def _turn(text: str) -> Turn:
    return Turn(
        turn_id="t1",
        role="user",
        content=text,
        ts=datetime.utcnow(),
        session_id="s1",
    )


def test_llm_extractor_parses_preferences_and_facts():
    runtime = StaticRuntime(
        """
        {
          "preferences": [
            {"key": "language.liked", "value": "python", "confidence": 0.91}
          ],
          "facts": [
            {
              "fact_id": "profile.allergy",
              "predicate": "allergy",
              "object": "đậu nành",
              "confidence": 0.88,
              "tags": ["profile", "allergy"]
            }
          ]
        }
        """
    )
    result = LLMStructuredExtractor(runtime).extract(_turn("text"), user_id="u")

    assert result.errors == []
    assert result.preferences[0].key == "language.liked"
    assert result.preferences[0].value == "python"
    assert result.facts[0].fact_id == "profile.allergy"
    assert result.facts[0].object == "đậu nành"


def test_llm_extractor_returns_error_on_invalid_json():
    runtime = StaticRuntime("not json")
    result = LLMStructuredExtractor(runtime).extract(_turn("text"), user_id="u")

    assert result.preferences == []
    assert result.facts == []
    assert result.errors
    assert result.errors[0]["kind"] == "parse"
