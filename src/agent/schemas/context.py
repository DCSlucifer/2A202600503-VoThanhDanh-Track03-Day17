from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Level = Literal["L0", "L1", "L2", "L3"]


class PriorityScore(BaseModel):
    value: float
    level_weight: float
    recency: float
    relevance: float
    pin: float


class ContextItem(BaseModel):
    item_id: str
    level: Level
    source: str  # "system" | "buffer" | "preference" | "fact" | "episode" | "semantic"
    source_id: Optional[str] = None
    text: str
    tokens: int
    score: Optional[PriorityScore] = None
    summarized: bool = False


class ContextPack(BaseModel):
    items: list[ContextItem] = Field(default_factory=list)
    tokens_per_level: dict[str, int] = Field(default_factory=dict)
    total_tokens: int = 0
    budget_tokens: int = 0
    headroom_tokens: int = 0
    dropped_ids: list[str] = Field(default_factory=list)
    summarized_ids: list[str] = Field(default_factory=list)
    degraded: bool = False  # True when ContextBudgetError forced L0-only pack

    def level_items(self, level: Level) -> list[ContextItem]:
        return [it for it in self.items if it.level == level]

    def render_prompt(self) -> str:
        """Render ordered context as a single prompt block."""
        sections: list[str] = []
        for level in ("L0", "L1", "L2", "L3"):
            items = self.level_items(level)  # type: ignore[arg-type]
            if not items:
                continue
            header = {
                "L0": "# System & current request",
                "L1": "# Recent dialogue",
                "L2": "# Recalled memory",
                "L3": "# Ambient context",
            }[level]
            body = "\n".join(it.text for it in items)
            sections.append(f"{header}\n{body}")
        return "\n\n".join(sections)
