from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

Role = Literal["user", "assistant", "system"]


class Turn(BaseModel):
    turn_id: str
    role: Role
    content: str
    ts: datetime
    session_id: str
    token_count: Optional[int] = None
    schema_version: int = SCHEMA_VERSION


class Session(BaseModel):
    session_id: str
    user_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    turn_count: int = 0
    schema_version: int = SCHEMA_VERSION


class ErrorRecord(BaseModel):
    node: str
    kind: str
    message: str
    ts: datetime = Field(default_factory=datetime.utcnow)
