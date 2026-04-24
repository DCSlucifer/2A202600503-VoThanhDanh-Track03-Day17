"""Benchmark orchestrator.

Replays each scenario once with memory enabled and once without, using the SAME
graph build (only the ``memory_enabled`` flag differs). Per-turn records are
scored with metrics.py, serialised to JSONL, and aggregated.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from agent.config import Settings, get_settings
from agent.graph import build_context, build_graph
from agent.schemas.benchmark import (
    MetricsReport,
    RunResult,
    Scenario,
    ScenarioTurn,
    TurnRecord,
)
from agent.utils.ids import run_id as make_run_id
from agent.utils.logging import JsonlLogger
from benchmark.metrics import ALL_METRICS, score_turn


@dataclass
class BenchmarkConfig:
    run_id: str
    scenarios_dir: Path
    run_dir: Path
    report_dir: Path
    scenario_ids: Optional[list[str]] = None


def load_scenarios(scenarios_dir: Path, ids: Optional[list[str]] = None) -> list[Scenario]:
    files = sorted(scenarios_dir.glob("*.yaml"))
    scenarios: list[Scenario] = []
    for path in files:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        scenario = Scenario.model_validate(raw)
        if ids and scenario.id not in ids:
            continue
        scenarios.append(scenario)
    return scenarios


def _run_scenario(
    scenario: Scenario,
    settings: Settings,
    run_id: str,
    memory_enabled: bool,
    turn_log_path: Path,
) -> RunResult:
    # Fresh context per (scenario, variant) — ensures memory isolation.
    ctx = build_context(settings)
    # Clean per-user state before starting
    user_id = settings.user.default_user_id
    try:
        ctx.redis.clear_user(user_id)
    except Exception:
        pass
    try:
        ctx.semantic.delete(user_id=user_id)
    except Exception:
        pass
    try:
        ctx.episodic.clear()
    except Exception:
        pass
    ctx.buffer.delete()

    ctx.turn_logger = JsonlLogger(turn_log_path)
    graph = build_graph(ctx)

    turn_records: list[TurnRecord] = []
    for session_idx, session_turns in enumerate(scenario.sessions):
        session_id = f"{scenario.id}_{'mem' if memory_enabled else 'nomem'}_s{session_idx}"
        # clear buffer per session (new session = fresh short-term memory)
        ctx.buffer.delete(session_id=session_id)
        for st in session_turns:
            turn_id = f"t_{uuid.uuid4().hex[:8]}"
            state = {
                "user_id": user_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "user_message": st.user,
                "flags": {
                    "memory_enabled": memory_enabled,
                    "run_id": run_id,
                    "scenario_id": scenario.id,
                    "session_idx": session_idx,
                    "turn_idx": st.turn_idx,
                },
                "errors": [],
                "latency_ms": {},
            }
            out = graph.invoke(state)
            record = _build_turn_record(
                scenario=scenario,
                scenario_turn=st,
                out=out,
                state=state,
                run_id=run_id,
                memory_enabled=memory_enabled,
            )
            turn_records.append(record)

    aggregates = _aggregate_records(turn_records, scenario)
    return RunResult(
        run_id=run_id,
        scenario_id=scenario.id,
        memory_enabled=memory_enabled,
        turn_records=turn_records,
        aggregates=aggregates,
    )


def _build_turn_record(
    scenario: Scenario,
    scenario_turn: ScenarioTurn,
    out: dict,
    state: dict,
    run_id: str,
    memory_enabled: bool,
) -> TurnRecord:
    llm_resp = out.get("llm_response") or {}
    record = TurnRecord(
        run_id=run_id,
        scenario_id=scenario.id,
        session_idx=state["flags"]["session_idx"],
        turn_idx=scenario_turn.turn_idx,
        user_id=state["user_id"],
        session_id=state["session_id"],
        memory_enabled=memory_enabled,
        user_message=state["user_message"],
        assistant_response=out.get("assistant_response", "") or "",
        router_trace=out.get("router_trace"),
        recall_counts={
            "preferences": len((out.get("recall") or {}).get("preferences", []) or []),
            "facts": len((out.get("recall") or {}).get("facts", []) or []),
            "episodes": len((out.get("recall") or {}).get("episodes", []) or []),
            "semantic": len((out.get("recall") or {}).get("semantic", []) or []),
        },
        context_pack_stats={
            "tokens_per_level": (out.get("context_pack") or {}).get("tokens_per_level", {}),
            "total_tokens": (out.get("context_pack") or {}).get("total_tokens", 0),
            "budget_tokens": (out.get("context_pack") or {}).get("budget_tokens", 0),
            "degraded": (out.get("context_pack") or {}).get("degraded", False),
        },
        usage=llm_resp.get("usage", {"prompt_tokens": 0, "completion_tokens": 0}),
        latency_ms=out.get("latency_ms", {}),
        persisted=out.get(
            "persisted",
            {
                "pref_writes": 0,
                "fact_writes": 0,
                "episode_writes": 0,
                "semantic_writes": 0,
            },
        ),
        errors=out.get("errors", []),
    )
    record.metrics = score_turn(record, scenario_turn)
    return record


def _aggregate_records(records: list[TurnRecord], scenario: Scenario) -> dict[str, float]:
    if not records:
        return {name: 0.0 for name in ALL_METRICS}
    out: dict[str, float] = {}
    for metric in ALL_METRICS:
        vals = [r.metrics.get(metric, 0.0) for r in records]
        out[metric] = round(sum(vals) / len(vals), 4)
    out["turns"] = len(records)
    prompt_total = sum((r.usage or {}).get("prompt_tokens", 0) for r in records)
    completion_total = sum((r.usage or {}).get("completion_tokens", 0) for r in records)
    out["prompt_tokens_total"] = prompt_total
    out["completion_tokens_total"] = completion_total
    return out


def _scenario_turns(scenario: Scenario) -> list[ScenarioTurn]:
    flat: list[ScenarioTurn] = []
    for sess in scenario.sessions:
        flat.extend(sess)
    return flat


def build_reports(
    mem_result: RunResult,
    nomem_result: RunResult,
    scenario: Scenario,
) -> MetricsReport:
    deltas = {
        metric: round(mem_result.aggregates.get(metric, 0.0)
                      - nomem_result.aggregates.get(metric, 0.0), 4)
        for metric in ALL_METRICS
    }
    return MetricsReport(
        scenario_id=scenario.id,
        with_mem={k: v for k, v in mem_result.aggregates.items()},
        no_mem={k: v for k, v in nomem_result.aggregates.items()},
        deltas=deltas,
        flags={"n_sessions": len(scenario.sessions)},
    )


def run_all(
    cfg: BenchmarkConfig, settings: Optional[Settings] = None
) -> tuple[list[tuple[Scenario, RunResult, RunResult]], list[MetricsReport]]:
    settings = settings or get_settings()
    scenarios = load_scenarios(cfg.scenarios_dir, cfg.scenario_ids)
    if not scenarios:
        raise RuntimeError(f"No scenarios found under {cfg.scenarios_dir}")

    cfg.run_dir.mkdir(parents=True, exist_ok=True)
    cfg.report_dir.mkdir(parents=True, exist_ok=True)

    results: list[tuple[Scenario, RunResult, RunResult]] = []
    reports: list[MetricsReport] = []

    for scenario in scenarios:
        mem_log = cfg.run_dir / f"{scenario.id}_mem.jsonl"
        nomem_log = cfg.run_dir / f"{scenario.id}_nomem.jsonl"
        if mem_log.exists():
            mem_log.unlink()
        if nomem_log.exists():
            nomem_log.unlink()

        mem_result = _run_scenario(
            scenario=scenario,
            settings=settings,
            run_id=cfg.run_id,
            memory_enabled=True,
            turn_log_path=mem_log,
        )
        nomem_result = _run_scenario(
            scenario=scenario,
            settings=settings,
            run_id=cfg.run_id,
            memory_enabled=False,
            turn_log_path=nomem_log,
        )
        report = build_reports(mem_result, nomem_result, scenario)
        results.append((scenario, mem_result, nomem_result))
        reports.append(report)

    return results, reports
