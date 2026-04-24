from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from agent.schemas.memory import Fact, Preference, PreferenceChange


class RedisMemory:
    """Durable long-term storage for preferences + facts.

    Key schema:
      agent:user:<uid>:pref:<slot>        -> preference JSON
      agent:user:<uid>:pref:index         -> set of slots
      agent:user:<uid>:fact:<fact_id>     -> fact JSON
      agent:user:<uid>:fact:index         -> set of fact_ids
    """

    name = "redis"

    def __init__(self, url: str, key_prefix: str = "agent", fact_default_ttl_days: int = 90,
                 use_fake: bool = False):
        self.key_prefix = key_prefix
        self.fact_default_ttl_days = fact_default_ttl_days
        if use_fake:
            import fakeredis  # type: ignore
            self.client = fakeredis.FakeRedis(decode_responses=True)
        else:
            import redis  # type: ignore
            self.client = redis.Redis.from_url(url, decode_responses=True)

    # ---------- helpers ----------

    def _pref_key(self, user_id: str, slot: str) -> str:
        return f"{self.key_prefix}:user:{user_id}:pref:{slot}"

    def _pref_index(self, user_id: str) -> str:
        return f"{self.key_prefix}:user:{user_id}:pref:index"

    def _fact_key(self, user_id: str, fact_id: str) -> str:
        return f"{self.key_prefix}:user:{user_id}:fact:{fact_id}"

    def _fact_index(self, user_id: str) -> str:
        return f"{self.key_prefix}:user:{user_id}:fact:index"

    # ---------- protocol ----------

    def health(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def read(
        self,
        user_id: str,
        kind: str = "preference",
        slot: Optional[str] = None,
        fact_id: Optional[str] = None,
        **_: Any,
    ) -> Any:
        if kind == "preference":
            if slot:
                return self._read_preference(user_id, slot)
            return self._read_all_preferences(user_id)
        if kind == "fact":
            if fact_id:
                return self._read_fact(user_id, fact_id)
            return self._read_all_facts(user_id)
        raise ValueError(f"unknown kind: {kind}")

    def write(self, obj: Any, **_: Any) -> Any:
        if isinstance(obj, Preference):
            return self._write_preference(obj)
        if isinstance(obj, Fact):
            return self._write_fact(obj)
        raise TypeError(f"RedisMemory accepts Preference|Fact, got {type(obj)}")

    def search(
        self,
        query: str,
        k: int = 5,
        user_id: Optional[str] = None,
        kind: str = "any",
        **_: Any,
    ) -> list[Any]:
        """Simple substring search over values (used as fallback in router)."""
        if not user_id:
            return []
        hits: list[Any] = []
        q = query.lower()
        if kind in ("any", "preference"):
            for pref in self._read_all_preferences(user_id):
                if q in pref.key.lower() or q in pref.value.lower():
                    hits.append(pref)
        if kind in ("any", "fact"):
            for fact in self._read_all_facts(user_id):
                blob = f"{fact.subject} {fact.predicate} {fact.object}".lower()
                if q in blob:
                    hits.append(fact)
        return hits[:k]

    def delete(
        self,
        user_id: str,
        kind: str = "preference",
        slot: Optional[str] = None,
        fact_id: Optional[str] = None,
        **_: Any,
    ) -> bool:
        if kind == "preference" and slot:
            self.client.delete(self._pref_key(user_id, slot))
            self.client.srem(self._pref_index(user_id), slot)
            return True
        if kind == "fact" and fact_id:
            self.client.delete(self._fact_key(user_id, fact_id))
            self.client.srem(self._fact_index(user_id), fact_id)
            return True
        return False

    def clear_user(self, user_id: str) -> None:
        for slot in list(self.client.smembers(self._pref_index(user_id)) or []):
            self.client.delete(self._pref_key(user_id, slot))
        self.client.delete(self._pref_index(user_id))
        for fid in list(self.client.smembers(self._fact_index(user_id)) or []):
            self.client.delete(self._fact_key(user_id, fid))
        self.client.delete(self._fact_index(user_id))

    # ---------- preferences ----------

    def _write_preference(self, pref: Preference) -> Preference:
        existing = self._read_preference(pref.user_id, pref.key)
        if existing and existing.value != pref.value:
            change = PreferenceChange(
                previous_value=existing.value,
                changed_at=datetime.utcnow(),
                source_turn_id=pref.source_turn_id,
            )
            pref.history = list(existing.history) + [change]
            # confidence decays when the user flips
            pref.confidence = max(0.5, pref.confidence - 0.1 * len(pref.history))
        elif existing:
            pref.history = list(existing.history)
        pref.updated_at = datetime.utcnow()
        self.client.set(self._pref_key(pref.user_id, pref.key), pref.model_dump_json())
        self.client.sadd(self._pref_index(pref.user_id), pref.key)
        return pref

    def _read_preference(self, user_id: str, slot: str) -> Optional[Preference]:
        raw = self.client.get(self._pref_key(user_id, slot))
        if not raw:
            return None
        return Preference.model_validate_json(raw)

    def _read_all_preferences(self, user_id: str) -> list[Preference]:
        slots = self.client.smembers(self._pref_index(user_id)) or []
        out: list[Preference] = []
        for slot in sorted(slots):
            p = self._read_preference(user_id, slot)
            if p:
                out.append(p)
        return out

    # ---------- facts ----------

    def _write_fact(self, fact: Fact) -> Fact:
        ttl_days = fact.ttl_days or self.fact_default_ttl_days
        self.client.set(
            self._fact_key(fact.user_id, fact.fact_id),
            fact.model_dump_json(),
            ex=ttl_days * 24 * 3600 if ttl_days else None,
        )
        self.client.sadd(self._fact_index(fact.user_id), fact.fact_id)
        return fact

    def _read_fact(self, user_id: str, fact_id: str) -> Optional[Fact]:
        raw = self.client.get(self._fact_key(user_id, fact_id))
        if not raw:
            return None
        return Fact.model_validate_json(raw)

    def _read_all_facts(self, user_id: str) -> list[Fact]:
        ids = self.client.smembers(self._fact_index(user_id)) or []
        out: list[Fact] = []
        for fid in sorted(ids):
            f = self._read_fact(user_id, fid)
            if f:
                out.append(f)
            else:
                # cleanup expired id from the index
                self.client.srem(self._fact_index(user_id), fid)
        return out
