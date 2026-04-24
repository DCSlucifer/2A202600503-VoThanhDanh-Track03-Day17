from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TypedDict

from agent.config import Settings
from agent.memory.buffer import BufferMemory
from agent.memory.conflict import ConflictResolver
from agent.memory.episodic import EpisodicMemory
from agent.memory.redis_store import RedisMemory
from agent.memory.semantic import SemanticMemory
from agent.memory.writers import EpisodeWriter, FactExtractor, PreferenceExtractor, SemanticWriter
from agent.services.context_manager import ContextManager
from agent.services.extraction import LLMStructuredExtractor
from agent.services.router import MemoryRouter
from agent.services.runtime.base import LLMRuntime
from agent.services.summarizer import Summarizer


class AgentState(TypedDict, total=False):
    # input
    user_id: str
    session_id: str
    turn_id: str
    user_message: str
    # running trace
    buffer: list[dict]  # serialized Turn dicts
    router_trace: Optional[dict]
    recall: Optional[dict]
    context_pack: Optional[dict]
    llm_response: Optional[dict]
    persisted: Optional[dict]
    errors: list[dict]
    flags: dict[str, Any]
    # pinned profile text injected into L0
    pinned_profile: Optional[str]
    assistant_response: Optional[str]
    # per-node latency in ms
    latency_ms: dict[str, float]


@dataclass
class AgentContext:
    """Bundle of services/backends closures capture. Constructed once per process."""
    settings: Settings
    buffer: BufferMemory
    redis: RedisMemory
    episodic: EpisodicMemory
    semantic: SemanticMemory
    router: MemoryRouter
    context_manager: ContextManager
    summarizer: Summarizer
    runtime: LLMRuntime
    preference_extractor: PreferenceExtractor
    fact_extractor: FactExtractor
    llm_extractor: LLMStructuredExtractor
    episode_writer: EpisodeWriter
    semantic_writer: SemanticWriter
    conflict_resolver: ConflictResolver
    turn_logger: Any = None  # set per-run by benchmark/CLI; optional
