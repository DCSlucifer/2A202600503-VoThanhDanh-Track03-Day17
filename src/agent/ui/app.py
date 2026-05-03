from __future__ import annotations

import json
import mimetypes
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from agent.config import Settings, get_settings
from agent.graph import build_context, build_graph
from agent.schemas.memory import Fact, Preference


STATIC_DIR = Path(__file__).with_name("static")


class AgentUiService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.ctx = build_context(self.settings)
        self.graph = build_graph(self.ctx)
        self._turn_idx = 0

    def ask(
        self,
        message: str,
        user_id: str,
        session_id: str,
        memory_enabled: bool = True,
        scenario_id: str = "ui",
        session_idx: int = 0,
    ) -> dict[str, Any]:
        self._turn_idx += 1
        state = {
            "user_id": user_id.strip() or self.settings.user.default_user_id,
            "session_id": session_id.strip() or f"ui_{uuid.uuid4().hex[:8]}",
            "turn_id": f"ui_{self._turn_idx}_{uuid.uuid4().hex[:6]}",
            "user_message": message,
            "flags": {
                "memory_enabled": bool(memory_enabled),
                "run_id": "ui",
                "scenario_id": scenario_id,
                "session_idx": session_idx,
                "turn_idx": self._turn_idx,
            },
            "errors": [],
            "latency_ms": {},
        }
        out = self.graph.invoke(state)
        return self._normalize_turn(out, state, bool(memory_enabled))

    def compare(self, message: str, user_id: str, session_id: str) -> dict[str, Any]:
        with_memory = self.ask(
            message=message,
            user_id=user_id,
            session_id=f"{session_id}_mem",
            memory_enabled=True,
            scenario_id="ui_compare",
            session_idx=0,
        )
        without_memory = self.ask(
            message=message,
            user_id=user_id,
            session_id=f"{session_id}_nomem",
            memory_enabled=False,
            scenario_id="ui_compare",
            session_idx=1,
        )
        return {
            "with_memory": with_memory,
            "without_memory": without_memory,
            "delta": {
                "prompt_tokens": (
                    with_memory["usage"].get("prompt_tokens", 0)
                    - without_memory["usage"].get("prompt_tokens", 0)
                ),
                "recall_items": (
                    sum(with_memory["recall_counts"].values())
                    - sum(without_memory["recall_counts"].values())
                ),
            },
        }

    def run_full_demo(self, user_id: Optional[str] = None) -> dict[str, Any]:
        uid = user_id or f"ui_demo_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        steps = [
            {
                "label": "Session 1: preference write",
                "result": self.ask(
                    "Tôi thích Python, không thích Java.",
                    uid,
                    "demo_s1",
                    True,
                    "ui_demo_pref",
                    0,
                ),
            },
            {
                "label": "Session 2: cross-session recall",
                "result": self.ask(
                    "Which language should I use for a simple script?",
                    uid,
                    "demo_s2",
                    True,
                    "ui_demo_cross_session",
                    1,
                ),
            },
            {
                "label": "Session 3: confusion episode",
                "result": self.ask(
                    "I'm confused about async/await in Python, I don't really get it.",
                    uid,
                    "demo_s3a",
                    True,
                    "ui_demo_episode",
                    2,
                ),
            },
            {
                "label": "Session 3: episode recall",
                "result": self.ask(
                    "Can you explain async/await again?",
                    uid,
                    "demo_s3b",
                    True,
                    "ui_demo_episode",
                    3,
                ),
            },
        ]
        comparisons = {
            "language": self.compare(
                "Which language should I use for a simple script?",
                uid,
                "demo_compare_language",
            ),
            "async": self.compare(
                "Can you explain async/await again?",
                uid,
                "demo_compare_async",
            ),
        }
        return {
            "user_id": uid,
            "steps": steps,
            "comparisons": comparisons,
            "memory": self.memory_snapshot(uid),
        }

    def memory_snapshot(self, user_id: str) -> dict[str, Any]:
        prefs = self.ctx.redis.read(user_id=user_id, kind="preference")
        facts = self.ctx.redis.read(user_id=user_id, kind="fact")
        episodes = self.ctx.episodic.read(user_id=user_id, limit=10)
        semantic_count = self.ctx.semantic.count()
        return {
            "preferences": [_model_dump(p) for p in prefs],
            "facts": [_model_dump(f) for f in facts],
            "episodes": [_model_dump(e) for e in episodes],
            "semantic_count": semantic_count,
        }

    def clear_user_memory(self, user_id: str) -> dict[str, Any]:
        """Wipe all 4 memory layers for a user. Useful for cold-start testing."""
        self.ctx.redis.clear_user(user_id)
        self.ctx.buffer.delete()  # clear all sessions
        self.ctx.episodic.clear()
        self.ctx.semantic.delete(user_id=user_id)
        return {"cleared": True, "user_id": user_id}

    def batch_ask(
        self,
        messages: list[str],
        user_id: str,
        session_id: str,
        memory_enabled: bool = True,
    ) -> dict[str, Any]:
        """Send multiple messages in sequence. Returns all turn results."""
        results: list[dict[str, Any]] = []
        for i, msg in enumerate(messages):
            r = self.ask(
                message=msg,
                user_id=user_id,
                session_id=session_id,
                memory_enabled=memory_enabled,
                scenario_id="ui_batch",
                session_idx=i,
            )
            results.append(r)
        return {
            "user_id": user_id,
            "session_id": session_id,
            "total_turns": len(results),
            "results": results,
        }

    def latest_report(self) -> dict[str, Any]:
        reports_root = Path(self.settings.benchmark.report_dir)
        runs = sorted(
            [p for p in reports_root.glob("run_*") if p.is_dir()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not runs:
            return {"available": False}
        latest = runs[0]
        summary_path = latest / "summary.json"
        report_path = latest / "report.md"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
        return {
            "available": True,
            "run_id": latest.name,
            "summary": summary,
            "report_excerpt": report[:6000],
            "paths": {
                "report": str(report_path),
                "metrics": str(latest / "metrics_table.csv"),
                "memory_hit_rate": str(latest / "memory_hit_rate.md"),
                "token_budget": str(latest / "token_budget.md"),
            },
        }

    def config(self) -> dict[str, Any]:
        return {
            "runtime": self.settings.runtime.mode,
            "model": self.settings.runtime.model,
            "embedding": self.settings.embedding.mode,
            "redis_url": self.settings.redis_url,
            "fake_redis": self.settings.use_fake_redis,
            "ephemeral_chroma": self.settings.use_ephemeral_chroma,
            "default_user": self.settings.user.default_user_id,
        }

    def _normalize_turn(
        self,
        out: dict[str, Any],
        state: dict[str, Any],
        memory_enabled: bool,
    ) -> dict[str, Any]:
        recall = out.get("recall") or {}
        router_trace = out.get("router_trace") or {}
        intents = router_trace.get("intents") or []
        top_intent = intents[0]["name"] if intents else "task_default"
        usage = (out.get("llm_response") or {}).get(
            "usage", {"prompt_tokens": 0, "completion_tokens": 0}
        )
        return {
            "user_id": state["user_id"],
            "session_id": state["session_id"],
            "message": state["user_message"],
            "memory_enabled": memory_enabled,
            "assistant_response": out.get("assistant_response", ""),
            "router": {
                "top_intent": top_intent,
                "matched_rules": router_trace.get("matched_rules", []),
                "backends": router_trace.get("backends", []),
                "fallback_used": router_trace.get("fallback_used", False),
            },
            "recall_counts": {
                "preferences": len(recall.get("preferences", []) or []),
                "facts": len(recall.get("facts", []) or []),
                "episodes": len(recall.get("episodes", []) or []),
                "semantic": len(recall.get("semantic", []) or []),
            },
            "persisted": out.get(
                "persisted",
                {
                    "pref_writes": 0,
                    "fact_writes": 0,
                    "episode_writes": 0,
                    "semantic_writes": 0,
                },
            ),
            "usage": usage,
            "latency_ms": out.get("latency_ms", {}),
            "context": {
                "tokens_per_level": (out.get("context_pack") or {}).get("tokens_per_level", {}),
                "total_tokens": (out.get("context_pack") or {}).get("total_tokens", 0),
                "degraded": (out.get("context_pack") or {}).get("degraded", False),
            },
            "errors": out.get("errors", []),
        }


def _model_dump(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (Preference, Fact)):
        return obj.model_dump(mode="json")
    return dict(obj)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    service = AgentUiService()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._serve_file(STATIC_DIR / "index.html")
                return
            if parsed.path.startswith("/static/"):
                rel = parsed.path.removeprefix("/static/")
                self._serve_file(STATIC_DIR / rel)
                return
            if parsed.path == "/api/config":
                self._json(service.config())
                return
            if parsed.path == "/api/report/latest":
                self._json(service.latest_report())
                return
            if parsed.path == "/api/memory":
                user_id = parse_qs(parsed.query).get("user_id", [""])[0]
                self._json(service.memory_snapshot(user_id))
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            body = self._read_json()
            try:
                if parsed.path == "/api/ask":
                    self._json(service.ask(
                        message=body.get("message", ""),
                        user_id=body.get("user_id", ""),
                        session_id=body.get("session_id", ""),
                        memory_enabled=body.get("memory_enabled", True),
                    ))
                    return
                if parsed.path == "/api/compare":
                    self._json(service.compare(
                        message=body.get("message", ""),
                        user_id=body.get("user_id", ""),
                        session_id=body.get("session_id", "compare"),
                    ))
                    return
                if parsed.path == "/api/demo/full":
                    self._json(service.run_full_demo(body.get("user_id") or None))
                    return
                if parsed.path == "/api/memory/clear":
                    self._json(service.clear_user_memory(
                        user_id=body.get("user_id", ""),
                    ))
                    return
                if parsed.path == "/api/batch":
                    self._json(service.batch_ask(
                        messages=body.get("messages", []),
                        user_id=body.get("user_id", ""),
                        session_id=body.get("session_id", "batch"),
                        memory_enabled=body.get("memory_enabled", True),
                    ))
                    return
            except Exception as exc:
                self._json({"error": str(exc)}, status=500)
                return
            self.send_error(404)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8") or "{}")

        def _json(self, data: Any, status: int = 200) -> None:
            payload = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _serve_file(self, path: Path) -> None:
            if not path.exists() or not path.is_file():
                self.send_error(404)
                return
            data = path.read_bytes()
            mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Agent UI running at http://{host}:{port}")
    server.serve_forever()
