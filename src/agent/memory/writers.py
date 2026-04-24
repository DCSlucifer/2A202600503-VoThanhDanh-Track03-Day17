"""Extractors that turn raw turns into typed memory objects."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from agent.schemas.core import Turn
from agent.schemas.memory import (
    Episode,
    EpisodeKind,
    Fact,
    Preference,
    SemanticChunk,
)
from agent.utils.ids import deterministic_id, new_id


@dataclass
class ExtractedPreference:
    key: str
    value: str
    confidence: float


# Regex-based preference extractor (VN + EN). Low recall on paraphrase; good enough
# for the benchmark scenarios. Extension hook left for a classifier replacement.
_PREF_POS_VN = re.compile(r"\bt[ôoóòỏõọơớờởỡợ]i\s+(?:rất\s+)?th[íi]ch\s+([\w\+\-#.]+)", re.IGNORECASE)
_PREF_NEG_VN = re.compile(
    r"\b(?:kh[oô]ng\s+th[íi]ch|gh[eé]t)\s+([\w\+\-#.]+)", re.IGNORECASE
)
_PREF_POS_EN = re.compile(r"\bi\s+(?:really\s+)?(?:like|prefer|love)\s+([\w\+\-#.]+)", re.IGNORECASE)
_PREF_NEG_EN = re.compile(r"\bi\s+(?:dislike|hate|don'?t\s+like)\s+([\w\+\-#.]+)", re.IGNORECASE)

_LANGUAGE_ALIASES = {
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
    "c++": "cpp",
    "c#": "csharp",
}


def _norm_language(raw: str) -> Optional[str]:
    """Accept a token, return canonical slug if it looks like a programming language."""
    t = raw.strip().lower().rstrip(".,!?;:")
    t = _LANGUAGE_ALIASES.get(t, t)
    langs = {
        "python", "java", "javascript", "typescript", "go", "rust", "cpp",
        "csharp", "ruby", "php", "kotlin", "swift", "scala", "haskell",
        "r", "elixir", "erlang", "lua",
    }
    return t if t in langs else None


class PreferenceExtractor:
    """Turn a user turn into zero or more Preference objects.

    The extractor is intentionally narrow: at Lab 17 we only capture programming
    language preferences reliably. The ``key`` namespace (``language.liked``,
    ``language.disliked``) is stable — extend by appending new namespaces later.
    """

    def extract(self, turn: Turn, user_id: str) -> list[Preference]:
        if turn.role != "user":
            return []
        msg = turn.content
        prefs: list[Preference] = []
        for pattern, polarity in (
            (_PREF_POS_VN, "liked"),
            (_PREF_POS_EN, "liked"),
            (_PREF_NEG_VN, "disliked"),
            (_PREF_NEG_EN, "disliked"),
        ):
            for m in pattern.finditer(msg):
                token = m.group(1)
                lang = _norm_language(token)
                if not lang:
                    continue
                key = f"language.{polarity}"
                prefs.append(
                    Preference(
                        user_id=user_id,
                        key=key,
                        value=lang,
                        confidence=0.9,
                        source_turn_id=turn.turn_id,
                        updated_at=datetime.utcnow(),
                    )
                )

        # collapse duplicates by (key, value)
        seen: set[tuple[str, str]] = set()
        unique: list[Preference] = []
        for p in prefs:
            key = (p.key, p.value)
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        return unique


# --- Fact extractor --------------------------------------------------------

_ALLERGY_VN_RE = re.compile(
    r"(?:t[ôo]i|mình|minh|toi)\s+(?:dị\s+ứng|di\s+ung)\s+(.+?)"
    r"(?:\s+chứ\s+không\s+phải|\s+chu\s+khong\s+phai|[.!?]|$)",
    re.IGNORECASE,
)
_ALLERGY_EN_RE = re.compile(
    r"(?:i(?:'m| am)? allergic to|my allergy is)\s+(.+?)"
    r"(?:\s+but\s+not|[.!?]|$)",
    re.IGNORECASE,
)
_NAME_VN_RE = re.compile(
    r"(?:tên\s+(?:của\s+)?t[ôo]i|t[ôo]i\s+tên|mình\s+tên)\s+là\s+(.+?)(?:[.!?]|$)",
    re.IGNORECASE,
)
_NAME_EN_RE = re.compile(r"\bmy name is\s+(.+?)(?:[.!?]|$)", re.IGNORECASE)
_ROLE_RE = re.compile(
    r"(?:my role is|my job is|vai trò của t[ôo]i là|công việc của t[ôo]i là)\s+(.+?)(?:[.!?]|$)",
    re.IGNORECASE,
)
_STACK_RE = re.compile(
    r"(?:i(?:'m| am)? using|t[ôo]i đang dùng|mình đang dùng)\s+(.+?)(?:[.!?]|$)",
    re.IGNORECASE,
)


def _clean_fact_value(raw: str, *, lowercase: bool = False) -> str:
    value = raw.strip()
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" \t\r\n,;:.!?")
    return value.lower() if lowercase else value


def _looks_like_question_value(value: str) -> bool:
    return value.lower() in {"gì", "gi", "what", "which", "nào", "nao"}


class FactExtractor:
    """Extract durable profile facts from user turns.

    The extractor intentionally targets a few high-value profile slots for Lab 17:
    allergy, name, role, and technical stack. Repeated writes use stable fact IDs,
    so corrections overwrite the old value instead of appending contradictions.
    """

    def extract(self, turn: Turn, user_id: str) -> list[Fact]:
        if turn.role != "user":
            return []
        msg = turn.content
        specs: list[tuple[str, str, str, list[str], str, bool]] = [
            ("profile.allergy", "allergy", "allergy", ["profile", "allergy"], "allergy", True),
            ("profile.name", "name", "name", ["profile", "identity"], "name", False),
            ("profile.role", "role", "role", ["profile", "work"], "role", False),
            ("profile.stack", "uses", "stack", ["profile", "technical"], "stack", False),
        ]
        matches: list[tuple[str, str, str, list[str], str, bool, str]] = []

        for pattern in (_ALLERGY_VN_RE, _ALLERGY_EN_RE):
            if m := pattern.search(msg):
                matches.append((*specs[0], m.group(1)))
        for pattern in (_NAME_VN_RE, _NAME_EN_RE):
            if m := pattern.search(msg):
                matches.append((*specs[1], m.group(1)))
        if m := _ROLE_RE.search(msg):
            matches.append((*specs[2], m.group(1)))
        if m := _STACK_RE.search(msg):
            matches.append((*specs[3], m.group(1)))

        facts: list[Fact] = []
        seen: set[str] = set()
        for fact_id, predicate, tag, tags, _slot, lowercase, value_raw in matches:
            value = _clean_fact_value(value_raw, lowercase=lowercase)
            if not value or _looks_like_question_value(value) or fact_id in seen:
                continue
            seen.add(fact_id)
            facts.append(
                Fact(
                    fact_id=fact_id,
                    user_id=user_id,
                    subject="user",
                    predicate=predicate,
                    object=value,
                    confidence=0.9,
                    source_turn_id=turn.turn_id,
                    ts=datetime.utcnow(),
                    tags=list(dict.fromkeys(tags + [tag])),
                )
            )
        return facts


# --- Episode writer --------------------------------------------------------

_CONFUSION_RE = re.compile(
    r"\b(confused|bối rối|kh[oô]ng hi[eể]u|don'?t (?:really )?get|stuck on|lost)\b",
    re.IGNORECASE,
)
_BREAKTHROUGH_RE = re.compile(
    r"\b(got it|finally understand|clear now|[àa] ra|[aá] ha|hi[eể]u r[oồ]i|makes sense now)\b",
    re.IGNORECASE,
)
_ERROR_RE = re.compile(
    r"\b(stack\s*trace|exception|traceback|error message|l[oỗ]i ch[aạ]y|crash(?:ed)?)\b",
    re.IGNORECASE,
)


def classify_episode(text: str) -> EpisodeKind:
    t = text.lower()
    if _CONFUSION_RE.search(t):
        return "confusion"
    if _BREAKTHROUGH_RE.search(t):
        return "breakthrough"
    if _ERROR_RE.search(t):
        return "error_recovery"
    return "turn"


def _extract_tags(user_text: str) -> list[str]:
    tags: list[str] = []
    # Keyword tags for programming topics — lightweight and deterministic.
    keywords = {
        "async/await": "async-await",
        "asyncio": "async-await",
        "promises": "async-await",
        "pointer": "pointers",
        "concurrency": "concurrency",
        "recursion": "recursion",
        "decorator": "decorators",
        "generic": "generics",
        "lambda": "lambdas",
    }
    low = user_text.lower()
    for needle, tag in keywords.items():
        if needle in low:
            tags.append(tag)
    return list(dict.fromkeys(tags))


class EpisodeWriter:
    """Turn each user/assistant exchange into an Episode for the JSONL log."""

    def build(
        self,
        user_turn: Turn,
        assistant_turn: Turn,
        user_id: str,
        session_id: str,
    ) -> Episode:
        kind = classify_episode(user_turn.content)
        tags = _extract_tags(user_turn.content)
        summary_prefix = {
            "confusion": "User showed confusion",
            "breakthrough": "User had a breakthrough",
            "error_recovery": "User reported an error",
            "turn": "User asked",
        }[kind]
        summary = f"{summary_prefix}: {user_turn.content.strip()[:140]}"
        excerpt = assistant_turn.content.strip()[:200]
        return Episode(
            episode_id=deterministic_id(session_id, str(user_turn.turn_id)),
            user_id=user_id,
            session_id=session_id,
            kind=kind,
            summary=summary,
            context_excerpt=excerpt,
            tags=tags,
            ts=user_turn.ts,
        )


# --- Semantic writer -------------------------------------------------------


class SemanticWriter:
    """Produce SemanticChunks for distillation. Kept small and deterministic.

    At Lab 17 we mirror (a) every preference write, and (b) notable episodes
    (kind != "turn") into the vector store. Raw turns are never embedded so the
    vector index stays clean.
    """

    def from_preference(self, pref: Preference) -> SemanticChunk:
        text = f"User preference: {pref.key} = {pref.value}"
        return SemanticChunk(
            chunk_id=deterministic_id(pref.user_id, pref.key, pref.value),
            user_id=pref.user_id,
            source_id=f"pref:{pref.key}",
            source_kind="preference",
            text=text,
            tags=[pref.key],
            ts=pref.updated_at,
        )

    def from_fact(self, fact: Fact) -> SemanticChunk:
        return SemanticChunk(
            chunk_id=deterministic_id("fact", fact.fact_id),
            user_id=fact.user_id,
            source_id=f"fact:{fact.fact_id}",
            source_kind="fact",
            text=fact.render(),
            tags=list(fact.tags),
            ts=fact.ts,
        )

    def from_episode(self, episode: Episode) -> Optional[SemanticChunk]:
        if episode.kind == "turn":
            return None
        return SemanticChunk(
            chunk_id=deterministic_id("episode", episode.episode_id),
            user_id=episode.user_id,
            source_id=f"episode:{episode.episode_id}",
            source_kind="episode",
            text=f"[{episode.kind}] {episode.summary}",
            tags=list(episode.tags),
            ts=episode.ts,
        )
