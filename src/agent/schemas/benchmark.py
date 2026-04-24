from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ScenarioTurn(BaseModel):
    turn_idx: int
    user: str
    expected_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    title: str
    category: str
    sessions: list[list[ScenarioTurn]]  # list of sessions; each session is a list of turns
    oracle_preferences: dict[str, str] = Field(default_factory=dict)
    oracle_facts: dict[str, str] = Field(default_factory=dict)
    notes: Optional[str] = None


class TurnRecord(BaseModel):
    run_id: str
    scenario_id: str
    session_idx: int
    turn_idx: int
    user_id: str
    session_id: str
    memory_enabled: bool
    user_message: str
    assistant_response: str
    router_trace: Optional[dict[str, Any]] = None
    recall_counts: dict[str, int] = Field(default_factory=dict)
    context_pack_stats: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    persisted: dict[str, int] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=datetime.utcnow)


class RunResult(BaseModel):
    run_id: str
    scenario_id: str
    memory_enabled: bool
    turn_records: list[TurnRecord]
    aggregates: dict[str, float] = Field(default_factory=dict)


class MetricsReport(BaseModel):
    scenario_id: str
    with_mem: dict[str, float]
    no_mem: dict[str, float]
    deltas: dict[str, float]
    flags: dict[str, Any] = Field(default_factory=dict)
