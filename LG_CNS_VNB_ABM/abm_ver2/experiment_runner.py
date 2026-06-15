#!/usr/bin/env python3
import argparse
import csv
import statistics
from pathlib import Path

from simulate import run_simulation


METRIC_COLUMNS = [
    "PRs per Engineer",
    "Lead Time (steps)",
    "Deployment Frequency",
    "Change Failure Rate (%)",
    "Recovery Time (steps)",
    "% Time on New Capabilities",
]

RESULT_COLUMNS = [
    "scenario_id",
    "condition_id",
    "run_id",
    "seed",
    "num_sprints",
    "review_strictness",
    "codebase_stability",
] + METRIC_COLUMNS


def scenario_b_conditions():
    conditions = []
    condition_index = 1
    for codebase_stability in [0.4, 0.8]:
        for review_strictness in [0.3, 0.5, 0.7, 0.9]:
            conditions.append({
                "scenario_id": "B",
                "condition_id": f"B{condition_index}",
                "review_strictness": review_strictness,
                "codebase_stability": codebase_stability,
            })
            condition_index += 1
    return conditions


def run_condition(condition, runs, num_sprints, seed_start, num_developers):
    rows = []
    for run_index in range(runs):
        seed = seed_start + run_index
        params = {
            "num_developers": num_developers,
            "num_sprints": num_sprints,
            "review_strictness": condition["review_strictness"],
            "codebase_stability": condition["codebase_stability"],
            "seed": seed,
        }
        result = run_simulation(params)
        prism = result.get("prism", {})

        row = {
            "scenario_id": condition["scenario_id"],
            "condition_id": condition["condition_id"],
            "run_id": run_index + 1,
            "seed": seed,
            "num_sprints": num_sprints,
            "review_strictness": condition["review_strictness"],
            "codebase_stability": condition["codebase_stability"],
        }
        for metric in METRIC_COLUMNS:
            row[metric] = prism.get(metric, "")
        rows.append(row)
    return rows


def summarize_results(rows):
    summary_rows = []
    grouped = {}
    for row in rows:
        grouped.setdefault(row["condition_id"], []).append(row)

    for condition_id in sorted(grouped, key=lambda value: int(value[1:])):
        condition_rows = grouped[condition_id]
        first = condition_rows[0]
        summary = {
            "scenario_id": first["scenario_id"],
            "condition_id": condition_id,
            "runs": len(condition_rows),
            "num_sprints": first["num_sprints"],
            "review_strictness": first["review_strictness"],
            "codebase_stability": first["codebase_stability"],
        }

        for metric in METRIC_COLUMNS:
            values = [float(row[metric]) for row in condition_rows if row[metric] != ""]
            summary[f"{metric} mean"] = statistics.mean(values) if values else ""
            summary[f"{metric} std"] = statistics.stdev(values) if len(values) > 1 else 0.0
        summary_rows.append(summary)
    return summary_rows


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args():
    parser = argparse.ArgumentParser(description="Run scenario-based ABM experiments.")
    parser.add_argument("--scenario", default="B", choices=["B"])
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--sprints", type=int, default=6)
    parser.add_argument("--seed-start", type=int, default=1000)
    parser.add_argument("--num-developers", type=int, default=9)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    return parser.parse_args()


def main():
    args = parse_args()
    rows = []
    for condition in scenario_b_conditions():
        rows.extend(
            run_condition(
                condition=condition,
                runs=args.runs,
                num_sprints=args.sprints,
                seed_start=args.seed_start,
                num_developers=args.num_developers,
            )
        )

    summary_rows = summarize_results(rows)
    summary_columns = [
        "scenario_id",
        "condition_id",
        "runs",
        "num_sprints",
        "review_strictness",
        "codebase_stability",
    ]
    for metric in METRIC_COLUMNS:
        summary_columns.extend([f"{metric} mean", f"{metric} std"])

    write_csv(args.output_dir / "experiment_results.csv", rows, RESULT_COLUMNS)
    write_csv(args.output_dir / "experiment_summary.csv", summary_rows, summary_columns)

    print(f"Wrote {len(rows)} run-level rows to {args.output_dir / 'experiment_results.csv'}")
    print(f"Wrote {len(summary_rows)} summary rows to {args.output_dir / 'experiment_summary.csv'}")


if __name__ == "__main__":
    main()
