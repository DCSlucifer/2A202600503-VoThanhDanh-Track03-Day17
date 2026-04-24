"""Config loader: YAML defaults + environment overrides."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()


DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "settings.yaml"


@dataclass
class RuntimeConfig:
    mode: str = "mock"          # "mock" | "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_tokens: int = 512
    seed: int = 17


@dataclass
class EmbeddingConfig:
    mode: str = "hash"          # "hash" | "openai"
    model: str = "text-embedding-3-small"
    dim: int = 128


@dataclass
class UserConfig:
    default_user_id: str = "demo_user"


@dataclass
class ContextConfig:
    budget_tokens: int = 8000
    response_headroom_tokens: int = 800
    split: dict[str, float] = field(
        default_factory=lambda: {"l0": 0.15, "l1": 0.35, "l2": 0.35, "l3": 0.05}
    )
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "level": 1.0,
            "recency": 0.3,
            "relevance": 0.7,
            "pin": 0.5,
        }
    )
    recency_tau_hours: float = 72.0
    buffer_recent_turns: int = 6


@dataclass
class RouterConfig:
    high_confidence_threshold: float = 0.8
    medium_confidence_threshold: float = 0.4
    fallback_top_k: int = 5
    max_backends_per_turn: int = 3


@dataclass
class BufferMemoryConfig:
    max_turns: int = 12


@dataclass
class RedisMemoryConfig:
    url_env: str = "REDIS_URL"
    key_prefix: str = "agent"
    fact_default_ttl_days: int = 90


@dataclass
class EpisodicMemoryConfig:
    log_dir: str = "./outputs/episodic"


@dataclass
class SemanticMemoryConfig:
    persist_dir: str = "./outputs/chroma"
    collection: str = "semantic_memory"
    distilled_top_k: int = 6


@dataclass
class MemoryConfig:
    extraction_mode: str = "rules"  # "rules" | "llm"
    buffer: BufferMemoryConfig = field(default_factory=BufferMemoryConfig)
    redis: RedisMemoryConfig = field(default_factory=RedisMemoryConfig)
    episodic: EpisodicMemoryConfig = field(default_factory=EpisodicMemoryConfig)
    semantic: SemanticMemoryConfig = field(default_factory=SemanticMemoryConfig)


@dataclass
class BenchmarkConfig:
    run_dir: str = "./outputs/runs"
    report_dir: str = "./outputs/reports"
    scenarios_dir: str = "./benchmark/scenarios"


@dataclass
class Settings:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    user: UserConfig = field(default_factory=UserConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    router: RouterConfig = field(default_factory=RouterConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)

    # runtime-populated extras
    openai_api_key: Optional[str] = None
    redis_url: str = "redis://localhost:6379/0"
    use_fake_redis: bool = False
    use_ephemeral_chroma: bool = False


def _merge(dst: Any, src: dict[str, Any]) -> None:
    for key, val in src.items():
        if not hasattr(dst, key):
            continue
        current = getattr(dst, key)
        if isinstance(val, dict) and hasattr(current, "__dataclass_fields__"):
            _merge(current, val)
        else:
            setattr(dst, key, val)


def _env_overrides(s: Settings) -> None:
    # Simple double-underscore env overrides: AGENT_RUNTIME__MODE=openai
    for env_key, env_val in os.environ.items():
        if not env_key.startswith("AGENT_"):
            continue
        path = env_key[len("AGENT_"):].lower().split("__")
        ref: Any = s
        try:
            for part in path[:-1]:
                ref = getattr(ref, part)
            leaf = path[-1]
            if not hasattr(ref, leaf):
                continue
            current = getattr(ref, leaf)
            cast_val: Any = env_val
            if isinstance(current, bool):
                cast_val = env_val.lower() in {"1", "true", "yes", "on"}
            elif isinstance(current, int):
                cast_val = int(env_val)
            elif isinstance(current, float):
                cast_val = float(env_val)
            setattr(ref, leaf, cast_val)
        except Exception:
            continue

    s.openai_api_key = os.environ.get("OPENAI_API_KEY") or s.openai_api_key
    s.redis_url = os.environ.get("REDIS_URL", s.redis_url)
    if os.environ.get("AGENT_USE_FAKE_REDIS", "").lower() in {"1", "true", "yes", "on"}:
        s.use_fake_redis = True
    if os.environ.get("AGENT_USE_EPHEMERAL_CHROMA", "").lower() in {"1", "true", "yes", "on"}:
        s.use_ephemeral_chroma = True


def load_settings(path: str | Path = DEFAULT_SETTINGS_PATH) -> Settings:
    p = Path(path)
    s = Settings()
    if p.exists():
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        _merge(s, data)
    _env_overrides(s)
    return s


_SINGLETON: Optional[Settings] = None


def get_settings() -> Settings:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = load_settings()
    return _SINGLETON


def reset_settings() -> None:
    global _SINGLETON
    _SINGLETON = None
