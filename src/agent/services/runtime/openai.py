from __future__ import annotations

import os
from typing import Any, Optional

from agent.services.runtime.base import LLMResponse


class OpenAIRuntime:
    name = "openai"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        seed: int = 17,
    ):
        from openai import OpenAI  # type: ignore
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def generate(self, prompt: str, **opts: Any) -> LLMResponse:
        model = opts.get("model", self.model)
        temperature = opts.get("temperature", self.temperature)
        max_tokens = opts.get("max_tokens", self.max_tokens)
        seed = opts.get("seed", self.seed)

        resp = self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
            messages=[
                {"role": "system",
                 "content": "You are a helpful assistant with persistent memory of the user. "
                            "If the prompt includes recalled preferences, episodes or facts, "
                            "use them naturally in your answer."},
                {"role": "user", "content": prompt},
            ],
        )
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResponse(
            content=choice.message.content or "",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            model=model,
            raw=resp,
        )
