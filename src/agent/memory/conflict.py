from __future__ import annotations

from agent.schemas.memory import Preference


class ConflictResolver:
    """Lab 17 rule: newer + higher confidence wins, keep audit trail.

    This is a stub that currently only handles Preference conflicts. Extend with
    more types (Facts, Episodes) when needed; API is intentionally small.
    """

    def merge_preference(self, existing: Preference, incoming: Preference) -> Preference:
        if existing.key != incoming.key or existing.user_id != incoming.user_id:
            raise ValueError("cannot merge preferences from different keys or users")
        if existing.value == incoming.value:
            existing.confidence = max(existing.confidence, incoming.confidence)
            existing.updated_at = incoming.updated_at
            return existing
        newer = incoming if incoming.updated_at >= existing.updated_at else existing
        older = existing if newer is incoming else incoming
        if newer.confidence < older.confidence - 0.2:
            return older
        return newer
