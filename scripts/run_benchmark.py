"""Entry-point: run all benchmark scenarios and write reports.

Usage:
  python -m scripts.run_benchmark                # mock runtime, all scenarios
  AGENT_RUNTIME__MODE=openai python -m scripts.run_benchmark
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ on sys.path when run as a script.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent.config import get_settings, reset_settings  # noqa: E402
from agent.utils.ids import run_id as make_run_id  # noqa: E402
from benchmark.runner import BenchmarkConfig, run_all  # noqa: E402
from benchmark.reporter import write_all_reports  # noqa: E402


def main() -> int:
    # If the user hasn't set up redis/chroma, allow graceful fallback to fake/ephemeral
    # by auto-flipping the toggle when their URLs look unreachable.
    os.environ.setdefault("AGENT_USE_FAKE_REDIS", "true")
    os.environ.setdefault("AGENT_USE_EPHEMERAL_CHROMA", "true")

    reset_settings()
    settings = get_settings()

    run_id = make_run_id()
    run_dir = Path(settings.benchmark.run_dir) / run_id
    report_dir = Path(settings.benchmark.report_dir) / run_id
    scenarios_dir = Path(settings.benchmark.scenarios_dir)

    print(f"[bench] run_id={run_id}")
    print(f"[bench] runtime.mode={settings.runtime.mode} model={settings.runtime.model}")
    print(f"[bench] scenarios_dir={scenarios_dir}")
    print(f"[bench] run_dir={run_dir}")
    print(f"[bench] report_dir={report_dir}")

    cfg = BenchmarkConfig(
        run_id=run_id,
        scenarios_dir=scenarios_dir,
        run_dir=run_dir,
        report_dir=report_dir,
    )
    results, reports = run_all(cfg, settings=settings)
    write_all_reports(run_id, report_dir, results, reports)

    print(f"[bench] done. {len(reports)} scenarios.")
    print(f"[bench] report: {report_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
