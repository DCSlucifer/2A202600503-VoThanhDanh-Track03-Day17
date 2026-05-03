from __future__ import annotations

from agent.schemas.memory import Preference, PreferenceChange


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
            # incoming is significantly less confident — keep older but log the attempt
            older.history = list(older.history) + [
                PreferenceChange(
                    previous_value=newer.value,
                    changed_at=newer.updated_at,
                    source_turn_id=newer.source_turn_id,
                )
            ]
            return older
        # newer wins; push older value into newer's history trail
        newer.history = list(older.history) + [
            PreferenceChange(
                previous_value=older.value,
                changed_at=older.updated_at,
                source_turn_id=older.source_turn_id,
            )
        ]
        # confidence decay when user flips repeatedly
        newer.confidence = max(0.5, newer.confidence - 0.1 * len(newer.history))
        return newer
