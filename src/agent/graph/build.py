from __future__ import annotations

from typing import Optional

from langgraph.graph import END, StateGraph

from agent.config import Settings, get_settings
from agent.graph.nodes import (
    make_ingest,
    make_llm,
    make_log_turn,
    make_persist,
    make_plan_context,
    make_recall,
    make_route_memory,
)
from agent.graph.state import AgentContext, AgentState
from agent.memory.buffer import BufferMemory
from agent.memory.conflict import ConflictResolver
from agent.memory.episodic import EpisodicMemory
from agent.memory.redis_store import RedisMemory
from agent.memory.semantic import SemanticMemory, hash_embedding
from agent.memory.writers import EpisodeWriter, FactExtractor, PreferenceExtractor, SemanticWriter
from agent.services.context_manager import ContextManager
from agent.services.extraction import LLMStructuredExtractor
from agent.services.router import MemoryRouter
from agent.services.runtime.base import LLMRuntime
from agent.services.runtime.mock import MockRuntime
from agent.services.runtime.openai import OpenAIRuntime
from agent.services.summarizer import Summarizer


def _build_embed_fn(settings: Settings):
    if settings.embedding.mode == "openai" and settings.openai_api_key:
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=settings.openai_api_key)
            model = settings.embedding.model

            def _embed(texts: list[str]) -> list[list[float]]:
                resp = client.embeddings.create(model=model, input=texts)
                return [d.embedding for d in resp.data]

            return _embed
        except Exception:
            pass
    return hash_embedding(dim=settings.embedding.dim)


def _build_runtime(settings: Settings) -> LLMRuntime:
    if settings.runtime.mode == "openai" and settings.openai_api_key:
        return OpenAIRuntime(
            model=settings.runtime.model,
            api_key=settings.openai_api_key,
            temperature=settings.runtime.temperature,
            max_tokens=settings.runtime.max_tokens,
            seed=settings.runtime.seed,
        )
    return MockRuntime(model="mock-" + settings.runtime.model, seed=settings.runtime.seed)


def build_context(settings: Optional[Settings] = None) -> AgentContext:
    s = settings or get_settings()

    buffer = BufferMemory(max_turns=s.memory.buffer.max_turns)
    redis = RedisMemory(
        url=s.redis_url,
        key_prefix=s.memory.redis.key_prefix,
        fact_default_ttl_days=s.memory.redis.fact_default_ttl_days,
        use_fake=s.use_fake_redis,
    )
    episodic = EpisodicMemory(log_dir=s.memory.episodic.log_dir)
    semantic = SemanticMemory(
        persist_dir=s.memory.semantic.persist_dir,
        collection=s.memory.semantic.collection,
        embed_fn=_build_embed_fn(s),
        ephemeral=s.use_ephemeral_chroma,
    )

    summarizer = Summarizer()
    router = MemoryRouter(cfg=s.router)
    context_manager = ContextManager(cfg=s.context, summarizer=summarizer)
    runtime = _build_runtime(s)

    return AgentContext(
        settings=s,
        buffer=buffer,
        redis=redis,
        episodic=episodic,
        semantic=semantic,
        router=router,
        context_manager=context_manager,
        summarizer=summarizer,
        runtime=runtime,
        preference_extractor=PreferenceExtractor(),
        fact_extractor=FactExtractor(),
        llm_extractor=LLMStructuredExtractor(runtime),
        episode_writer=EpisodeWriter(),
        semantic_writer=SemanticWriter(),
        conflict_resolver=ConflictResolver(),
    )


def build_graph(ctx: AgentContext):
    g = StateGraph(AgentState)

    g.add_node("ingest", make_ingest(ctx))
    g.add_node("route_memory", make_route_memory(ctx))
    g.add_node("recall", make_recall(ctx))
    g.add_node("plan_context", make_plan_context(ctx))
    g.add_node("llm", make_llm(ctx))
    g.add_node("persist", make_persist(ctx))
    g.add_node("log_turn", make_log_turn(ctx))

    g.set_entry_point("ingest")

    def _after_ingest(state: AgentState) -> str:
        flags = state.get("flags", {}) or {}
        return "route_memory" if flags.get("memory_enabled", True) else "plan_context"

    g.add_conditional_edges(
        "ingest",
        _after_ingest,
        {"route_memory": "route_memory", "plan_context": "plan_context"},
    )
    g.add_edge("route_memory", "recall")
    g.add_edge("recall", "plan_context")
    g.add_edge("plan_context", "llm")

    def _after_llm(state: AgentState) -> str:
        flags = state.get("flags", {}) or {}
        errors = state.get("errors", []) or []
        has_fatal = any(err.get("node") == "llm" for err in errors)
        if has_fatal or not flags.get("memory_enabled", True):
            return "log_turn"
        return "persist"

    g.add_conditional_edges(
        "llm",
        _after_llm,
        {"persist": "persist", "log_turn": "log_turn"},
    )
    g.add_edge("persist", "log_turn")
    g.add_edge("log_turn", END)

    return g.compile()
