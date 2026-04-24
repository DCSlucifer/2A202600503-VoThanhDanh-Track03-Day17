"""Generate Markdown + CSV reports from benchmark results."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from agent.schemas.benchmark import MetricsReport, RunResult, Scenario
from benchmark.metrics import ALL_METRICS


def write_all_reports(
    run_id: str,
    report_dir: Path,
    results: list[tuple[Scenario, RunResult, RunResult]],
    reports: list[MetricsReport],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_main_report(report_dir / "report.md", run_id, reports, results)
    _write_metrics_csv(report_dir / "metrics_table.csv", reports)
    _write_token_budget(report_dir / "token_budget.md", results)
    _write_memory_hit_rate(report_dir / "memory_hit_rate.md", results)
    deep_dir = report_dir / "scenario_deep_dives"
    deep_dir.mkdir(exist_ok=True)
    # Write a deep dive for each of the 4 required demo scenarios
    for scenario, mem, nomem in results:
        (deep_dir / f"{scenario.id}.md").write_text(
            _deep_dive(scenario, mem, nomem), encoding="utf-8"
        )
    # Summary JSON for programmatic consumers
    summary = {
        "run_id": run_id,
        "scenarios": [
            {
                "id": r.scenario_id,
                "with_mem": r.with_mem,
                "no_mem": r.no_mem,
                "deltas": r.deltas,
            }
            for r in reports
        ],
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))


# -----------------------------------------------------------------------------


def _write_main_report(
    path: Path, run_id: str, reports: list[MetricsReport],
    results: list[tuple[Scenario, RunResult, RunResult]],
) -> None:
    lines = [f"# Benchmark report — run `{run_id}`", "", "## Aggregate (averages per scenario)", ""]
    lines.append("| # | Scenario | Memory | "
                 "Relevance | Context util | Tok. eff. | Hit rate | Satisfaction |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for idx, r in enumerate(reports, start=1):
        lines.append(
            f"| {idx} | {r.scenario_id} | with |  "
            f"{r.with_mem.get('response_relevance', 0):.2f} | "
            f"{r.with_mem.get('context_utilization', 0):.2f} | "
            f"{r.with_mem.get('token_efficiency', 0):.3f} | "
            f"{r.with_mem.get('memory_hit_rate', 0):.2f} | "
            f"{r.with_mem.get('user_satisfaction_proxy', 0):.2f} |"
        )
        lines.append(
            f"| {idx} | {r.scenario_id} | no  |  "
            f"{r.no_mem.get('response_relevance', 0):.2f} | "
            f"{r.no_mem.get('context_utilization', 0):.2f} | "
            f"{r.no_mem.get('token_efficiency', 0):.3f} | "
            f"{r.no_mem.get('memory_hit_rate', 0):.2f} | "
            f"{r.no_mem.get('user_satisfaction_proxy', 0):.2f} |"
        )
    lines.append("")
    lines.append("## Deltas (with-mem − no-mem, averaged over turns)")
    lines.append("")
    lines.append("| Scenario | Δ relevance | Δ context util | Δ tok. eff. | Δ hit rate | Δ satisfaction |")
    lines.append("|---|---|---|---|---|---|")
    wins = 0
    for r in reports:
        scenario_wins = sum(
            1 for k in ("response_relevance", "context_utilization", "token_efficiency",
                        "memory_hit_rate", "user_satisfaction_proxy")
            if r.deltas.get(k, 0) > 0
        )
        if scenario_wins >= 3:
            wins += 1
        lines.append(
            f"| {r.scenario_id} | "
            f"{r.deltas.get('response_relevance', 0):+.3f} | "
            f"{r.deltas.get('context_utilization', 0):+.3f} | "
            f"{r.deltas.get('token_efficiency', 0):+.4f} | "
            f"{r.deltas.get('memory_hit_rate', 0):+.3f} | "
            f"{r.deltas.get('user_satisfaction_proxy', 0):+.3f} |"
        )
    lines.append("")
    lines.append(f"**With-mem wins ≥ 3/5 metrics on {wins}/{len(reports)} scenarios.**")
    lines.append("")
    lines.append("## Per-scenario turn counts")
    lines.append("")
    lines.append("| Scenario | Turns | Sessions | With-mem prompt tokens | No-mem prompt tokens |")
    lines.append("|---|---|---|---|---|")
    for scenario, mem, nomem in results:
        turn_count = sum(len(s) for s in scenario.sessions)
        lines.append(
            f"| {scenario.id} | {turn_count} | {len(scenario.sessions)} | "
            f"{mem.aggregates.get('prompt_tokens_total', 0)} | "
            f"{nomem.aggregates.get('prompt_tokens_total', 0)} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_metrics_csv(path: Path, reports: list[MetricsReport]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        header = ["scenario_id", "variant"]
        for m in ALL_METRICS:
            header.append(m)
        writer.writerow(header)
        for r in reports:
            for variant, vals in (("with_mem", r.with_mem), ("no_mem", r.no_mem)):
                row = [r.scenario_id, variant]
                for m in ALL_METRICS:
                    row.append(f"{vals.get(m, 0.0):.4f}")
                writer.writerow(row)


def _write_token_budget(
    path: Path, results: list[tuple[Scenario, RunResult, RunResult]],
) -> None:
    lines = ["# Token budget breakdown", "",
             "| Scenario | Variant | Avg L0 | Avg L1 | Avg L2 | Avg L3 | Avg total | Budget |",
             "|---|---|---|---|---|---|---|---|"]
    for scenario, mem, nomem in results:
        for name, res in (("with", mem), ("no", nomem)):
            if not res.turn_records:
                continue
            l0 = l1 = l2 = l3 = total = budget = 0.0
            n = len(res.turn_records)
            for rec in res.turn_records:
                tpl = (rec.context_pack_stats or {}).get("tokens_per_level", {}) or {}
                l0 += tpl.get("L0", 0)
                l1 += tpl.get("L1", 0)
                l2 += tpl.get("L2", 0)
                l3 += tpl.get("L3", 0)
                total += (rec.context_pack_stats or {}).get("total_tokens", 0)
                budget += (rec.context_pack_stats or {}).get("budget_tokens", 0)
            lines.append(
                f"| {scenario.id} | {name}-mem | "
                f"{l0/n:.0f} | {l1/n:.0f} | {l2/n:.0f} | {l3/n:.0f} | "
                f"{total/n:.0f} | {budget/n:.0f} |"
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_memory_hit_rate(
    path: Path, results: list[tuple[Scenario, RunResult, RunResult]],
) -> None:
    lines = ["# Memory hit rate", "",
             "Counts are per-turn averages across the scenario.", "",
             "| Scenario | Variant | Prefs | Facts | Episodes | Semantic | Overall hit rate |",
             "|---|---|---|---|---|---|---|"]
    for scenario, mem, nomem in results:
        for name, res in (("with", mem), ("no", nomem)):
            if not res.turn_records:
                continue
            n = len(res.turn_records)
            p = f = e = s = 0.0
            hit_sum = 0.0
            for rec in res.turn_records:
                rc = rec.recall_counts or {}
                p += rc.get("preferences", 0)
                f += rc.get("facts", 0)
                e += rc.get("episodes", 0)
                s += rc.get("semantic", 0)
                hit_sum += rec.metrics.get("memory_hit_rate", 0.0)
            lines.append(
                f"| {scenario.id} | {name}-mem | {p/n:.2f} | {f/n:.2f} | "
                f"{e/n:.2f} | {s/n:.2f} | {hit_sum/n:.2f} |"
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def _deep_dive(scenario: Scenario, mem: RunResult, nomem: RunResult) -> str:
    out: list[str] = [f"# Deep dive — {scenario.id}", "",
                      f"**Title**: {scenario.title}",
                      f"**Category**: {scenario.category}", ""]
    if scenario.notes:
        out.append(f"> {scenario.notes}")
        out.append("")
    out.append("## Aggregates")
    out.append("")
    out.append("| Metric | With-mem | No-mem | Δ |")
    out.append("|---|---|---|---|")
    for m in ALL_METRICS:
        w = mem.aggregates.get(m, 0.0)
        n = nomem.aggregates.get(m, 0.0)
        out.append(f"| {m} | {w:.3f} | {n:.3f} | {w-n:+.3f} |")
    out.append("")
    out.append("## Turn-by-turn (with-mem)")
    out.append("")
    for rec in mem.turn_records:
        resp = rec.assistant_response.replace("\n", " ")
        out.append(f"**Session {rec.session_idx} / Turn {rec.turn_idx}** — user: _{rec.user_message}_")
        out.append(f"> {resp}")
        out.append(
            f"- recall: prefs={rec.recall_counts.get('preferences',0)} "
            f"facts={rec.recall_counts.get('facts',0)} "
            f"episodes={rec.recall_counts.get('episodes',0)} "
            f"semantic={rec.recall_counts.get('semantic',0)} "
            f"· relevance={rec.metrics.get('response_relevance',0):.2f} "
            f"· hit={rec.metrics.get('memory_hit_rate',0):.2f}"
        )
        out.append("")
    out.append("## Turn-by-turn (no-mem)")
    out.append("")
    for rec in nomem.turn_records:
        resp = rec.assistant_response.replace("\n", " ")
        out.append(f"**Session {rec.session_idx} / Turn {rec.turn_idx}** — user: _{rec.user_message}_")
        out.append(f"> {resp}")
        out.append(
            f"- relevance={rec.metrics.get('response_relevance',0):.2f}"
        )
        out.append("")
    return "\n".join(out)
