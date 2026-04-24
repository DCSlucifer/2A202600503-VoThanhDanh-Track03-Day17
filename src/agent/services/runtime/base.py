from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    raw: Any = None
    extra: dict[str, Any] = field(default_factory=dict)


class LLMRuntime(Protocol):
    name: str
    model: str

    def generate(self, prompt: str, **opts: Any) -> LLMResponse: ...
