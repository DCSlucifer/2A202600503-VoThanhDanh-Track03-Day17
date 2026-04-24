"""End-to-end: run one benchmark scenario and assert artifacts exist."""
from pathlib import Path

from agent.config import reset_settings, get_settings
from agent.utils.ids import run_id as make_run_id
from benchmark.runner import BenchmarkConfig, run_all
from benchmark.reporter import write_all_reports


def test_runs_scenarios_and_writes_reports(tmp_outputs_dir, tmp_path: Path):
    reset_settings()
    settings = get_settings()

    run_id = make_run_id()
    run_dir = tmp_path / "runs" / run_id
    report_dir = tmp_path / "reports" / run_id

    cfg = BenchmarkConfig(
        run_id=run_id,
        scenarios_dir=Path(settings.benchmark.scenarios_dir),
        run_dir=run_dir,
        report_dir=report_dir,
        scenario_ids=["s02_pref_cross_session", "s06_episodic_adaptation", "s10_cold_start"],
    )
    results, reports = run_all(cfg, settings=settings)
    assert len(results) == 3
    write_all_reports(run_id, report_dir, results, reports)

    assert (report_dir / "report.md").exists()
    assert (report_dir / "metrics_table.csv").exists()
    assert (report_dir / "token_budget.md").exists()
    assert (report_dir / "memory_hit_rate.md").exists()
    deep = report_dir / "scenario_deep_dives"
    assert deep.exists()
    assert any(deep.iterdir())


def test_with_mem_wins_on_cross_session(tmp_outputs_dir, tmp_path: Path):
    """Sanity check: the scenario explicitly designed to expose memory benefit
    must show a positive delta on relevance for the with-mem variant."""
    reset_settings()
    settings = get_settings()
    run_id = make_run_id()
    cfg = BenchmarkConfig(
        run_id=run_id,
        scenarios_dir=Path(settings.benchmark.scenarios_dir),
        run_dir=tmp_path / "runs" / run_id,
        report_dir=tmp_path / "reports" / run_id,
        scenario_ids=["s02_pref_cross_session"],
    )
    _, reports = run_all(cfg, settings=settings)
    assert len(reports) == 1
    r = reports[0]
    assert r.deltas.get("response_relevance", 0) > 0, r.deltas
