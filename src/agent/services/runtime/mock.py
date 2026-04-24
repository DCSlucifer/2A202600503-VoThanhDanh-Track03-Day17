"""Deterministic mock runtime.

The mock inspects the prompt for memory markers and generates a response that
produces measurably different assistant behavior when memory items are present
vs. absent. This is what makes the with-mem vs no-mem benchmark meaningful
without burning OpenAI tokens.

Response grammar (priority order):
  1. If prompt contains ``[preference] language.liked = <X>`` → mention <X>.
  2. If prompt contains ``[preference] language.disliked = <Y>`` → avoid <Y>.
  3. If prompt contains ``[episode:confusion]`` about a topic → use simpler tone.
  4. If prompt contains ``[fact]`` → weave the fact into the response.
  5. Otherwise, fall back to a generic template per user intent keyword.
"""
from __future__ import annotations

import hashlib
import random
import re
from typing import Any

from agent.services.runtime.base import LLMResponse
from agent.services.tokenizer import count_tokens


_PREF_LIKED_RE = re.compile(
    r"(?:\[preference\]|User preference:)\s*language\.liked\s*=\s*(\w+)",
    re.IGNORECASE,
)
_PREF_DISLIKED_RE = re.compile(
    r"(?:\[preference\]|User preference:)\s*language\.disliked\s*=\s*(\w+)",
    re.IGNORECASE,
)
_CONFUSION_TAG_RE = re.compile(r"\[(?:episode:)?confusion\]\s+([^\n]+)")
_FACT_RE = re.compile(r"\[fact\]\s+([^\n]+)")
_USER_MSG_RE = re.compile(r"^User:\s*(.+)$", re.MULTILINE)
_FACT_CAPTURE_RE = re.compile(
    r"(?:\bmy name is\b|\bmy role is\b|\bi(?:'m| am)? using\b|"
    r"\bt[ôo]i đang dùng\b|\bt[ôo]i dị ứng\b|\bdi ung\b|\ballergic to\b)",
    re.IGNORECASE,
)
_ALLERGY_FACT_RE = re.compile(r"user\s+allergy\s+(.+?)(?:\s+\(conf|$)", re.IGNORECASE)
_STACK_FACT_RE = re.compile(r"user\s+uses\s+(.+?)(?:\s+\(conf|$)", re.IGNORECASE)
_SIMPLE_WORDS = [
    "let me break this down",
    "step by step",
    "think of it like this",
    "in simple terms",
]


class MockRuntime:
    name = "mock"

    def __init__(self, model: str = "mock-llm-0", seed: int = 17):
        self.model = model
        self.seed = seed

    def generate(self, prompt: str, **opts: Any) -> LLMResponse:
        seed = int(opts.get("seed", self.seed))
        rng = random.Random(
            seed * 100003
            + int(hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8], 16)
        )

        liked = _PREF_LIKED_RE.search(prompt)
        disliked = _PREF_DISLIKED_RE.search(prompt)
        confusion = _CONFUSION_TAG_RE.search(prompt)
        facts = _FACT_RE.findall(prompt)
        user_matches = _USER_MSG_RE.findall(prompt)
        user_message = user_matches[-1].strip() if user_matches else ""

        parts: list[str] = []

        low_user = user_message.lower()
        uses_code = any(kw in low_user for kw in ["code", "write", "implement", "function",
                                                   "script", "class", "algorithm", "viết"])
        asks_language = any(kw in low_user for kw in ["language", "ngôn ngữ", "which", "nên dùng",
                                                      "should i use", "recommend"])

        if confusion:
            raw_topic = confusion.group(1).strip()
            topic = re.sub(r"^User showed confusion:\s*", "", raw_topic, flags=re.IGNORECASE)
            topic = re.sub(r"^I(?:'m|\s+am|\s+was)\s+(?:really\s+)?confused\s+(?:about\s+)?",
                           "", topic, flags=re.IGNORECASE)
            topic = topic.rstrip(".!,;: ")
            simple = rng.choice(_SIMPLE_WORDS)
            parts.append(
                f"I remember you found {topic} tricky before, so {simple}: "
                f"I'll keep the explanation beginner-friendly."
            )

        if liked and (asks_language or uses_code):
            lang = liked.group(1).capitalize()
            parts.append(
                f"Going with {lang} since you've told me you prefer it."
            )
            if uses_code and lang.lower() == "python":
                parts.append(
                    "Here's a short Python sketch:\n"
                    "```python\n"
                    "def solve(x):\n"
                    "    return x  # replace with your logic\n"
                    "```"
                )

        if disliked:
            lang = disliked.group(1).capitalize()
            parts.append(f"I'll avoid {lang} because you've mentioned you don't like it.")

        if facts:
            fact_text = facts[0].strip()
            allergy = _ALLERGY_FACT_RE.search(fact_text)
            stack = _STACK_FACT_RE.search(fact_text)
            if allergy and any(kw in low_user for kw in ["allerg", "dị ứng", "di ung"]):
                parts.append(f"You are allergic to {allergy.group(1).strip()}.")
            elif stack and any(kw in low_user for kw in ["using", "version", "stack", "database"]):
                parts.append(f"You're using {stack.group(1).strip()}.")
            else:
                parts.append(f"Noted from your earlier notes: {fact_text}.")

        if not parts:
            if asks_language:
                parts.append(
                    "I don't have a saved preference yet — could you tell me which language you'd like to use?"
                )
            elif _FACT_CAPTURE_RE.search(low_user) and not any(q in low_user for q in [" gì", " what", "?"]):
                parts.append("Got it - noting that fact for later.")
            elif "thích" in low_user or "prefer" in low_user or "like" in low_user:
                parts.append("Got it — noting that preference for later.")
            else:
                parts.append(
                    f"Here's a generic response to: {user_message[:120]}" if user_message
                    else "Hello — how can I help?"
                )

        content = " ".join(p for p in parts if p)
        prompt_tokens = count_tokens(prompt, self.model)
        completion_tokens = count_tokens(content, self.model)
        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model,
            raw=None,
        )
