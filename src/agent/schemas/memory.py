from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent.schemas.core import SCHEMA_VERSION

EpisodeKind = Literal[
    "turn", "confusion", "breakthrough", "error_recovery", "tool_call"
]


class PreferenceChange(BaseModel):
    previous_value: str
    changed_at: datetime
    source_turn_id: Optional[str] = None


class Preference(BaseModel):
    user_id: str
    key: str  # "language.liked", "language.disliked", "tone", ...
    value: str
    confidence: float = 1.0
    source_turn_id: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    history: list[PreferenceChange] = Field(default_factory=list)
    schema_version: int = SCHEMA_VERSION


class Fact(BaseModel):
    fact_id: str
    user_id: str
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source_turn_id: Optional[str] = None
    ts: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = Field(default_factory=list)
    ttl_days: Optional[int] = None
    schema_version: int = SCHEMA_VERSION

    def render(self) -> str:
        return f"{self.subject} {self.predicate} {self.object}"


class Episode(BaseModel):
    episode_id: str
    user_id: str
    session_id: str
    kind: EpisodeKind = "turn"
    summary: str
    context_excerpt: Optional[str] = None
    outcome: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    ts: datetime = Field(default_factory=datetime.utcnow)
    schema_version: int = SCHEMA_VERSION


class SemanticChunk(BaseModel):
    chunk_id: str
    user_id: Optional[str] = None
    source_id: str  # id of the source fact/episode/summary
    source_kind: Literal["fact", "episode", "summary", "preference"]
    text: str
    ts: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = Field(default_factory=list)
    score: Optional[float] = None  # populated at retrieval time
    schema_version: int = SCHEMA_VERSION
