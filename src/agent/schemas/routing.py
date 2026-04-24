from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agent.schemas.memory import Preference, Fact, Episode, SemanticChunk

IntentName = Literal[
    "preference_recall",
    "factual_recall",
    "experience_recall",
    "preference_capture",
    "fact_capture",
    "task_default",
]

BackendName = Literal["buffer", "redis_pref", "redis_fact", "episodic", "semantic"]


class IntentScore(BaseModel):
    name: IntentName
    score: float


class RouterDecision(BaseModel):
    input: str
    intents: list[IntentScore]
    backends: list[BackendName]
    fallback_used: bool = False
    elapsed_ms: float = 0.0
    matched_rules: list[str] = Field(default_factory=list)


class RecallResult(BaseModel):
    preferences: list[Preference] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    episodes: list[Episode] = Field(default_factory=list)
    semantic: list[SemanticChunk] = Field(default_factory=list)
    decision: RouterDecision

    def total_items(self) -> int:
        return (
            len(self.preferences)
            + len(self.facts)
            + len(self.episodes)
            + len(self.semantic)
        )
