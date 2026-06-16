#!/usr/bin/env python3
"""Run final A/B/C experiments and preserve their CSV outputs."""
from pathlib import Path
import shutil
import subprocess
import sys


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
FINAL_DIR = OUTPUT_DIR / "final"
SCENARIOS = ("A", "B", "C")


def require_output(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required experiment output not found: {path}")


def copy_scenario_outputs(scenario_id: str) -> None:
    summary_src = OUTPUT_DIR / "experiment_summary.csv"
    results_src = OUTPUT_DIR / "experiment_results.csv"
    require_output(summary_src)
    require_output(results_src)

    summary_dst = FINAL_DIR / f"scenario_{scenario_id}_summary.csv"
    results_dst = FINAL_DIR / f"scenario_{scenario_id}_results.csv"
    shutil.copy2(summary_src, summary_dst)
    shutil.copy2(results_src, results_dst)
    print(f"Saved Scenario {scenario_id} summary: {summary_dst}", flush=True)
    print(f"Saved Scenario {scenario_id} results: {results_dst}", flush=True)


def run_scenario(scenario_id: str) -> None:
    print(f"Running Scenario {scenario_id} final experiment...", flush=True)
    subprocess.run(
        [
            sys.executable,
            "experiment_runner.py",
            "--scenario",
            scenario_id,
            "--runs",
            "100",
            "--sprints",
            "6",
            "--seed-start",
            "1000",
        ],
        cwd=BASE_DIR,
        check=True,
    )
    copy_scenario_outputs(scenario_id)


def main() -> None:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    for scenario_id in SCENARIOS:
        run_scenario(scenario_id)
    print(f"Final experiment outputs are stored in: {FINAL_DIR}", flush=True)


if __name__ == "__main__":
    main()
