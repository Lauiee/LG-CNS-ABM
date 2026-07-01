#!/usr/bin/env python3
"""Lightweight sanity checks for Scenario F/G behavior."""
import argparse
import statistics
from collections import defaultdict

from experiment_runner import get_conditions, run_condition


DEFAULT_RUNS = 10
DEFAULT_SPRINTS = 3
DEFAULT_SEED_START = 7000
DEFAULT_NUM_DEVELOPERS = 9


def to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run_scenario(scenario_id: str, runs: int, sprints: int, seed_start: int, num_developers: int):
    rows = []
    for condition in get_conditions(scenario_id):
        rows.extend(
            run_condition(
                condition=condition,
                runs=runs,
                num_sprints=sprints,
                seed_start=seed_start,
                num_developers=num_developers,
            )
        )
    return rows


def mean_by(rows: list[dict], group_column: str, metric: str) -> dict[str, float]:
    grouped = defaultdict(list)
    for row in rows:
        group_value = row.get(group_column)
        metric_value = to_float(row.get(metric))
        if group_value and metric_value is not None:
            grouped[group_value].append(metric_value)
    return {
        group_value: statistics.mean(values)
        for group_value, values in grouped.items()
        if values
    }


def fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def metric_pair(metrics: dict[str, float], left: str, right: str) -> tuple[float | None, float | None]:
    return metrics.get(left), metrics.get(right)


def print_check(name: str, passed: bool, detail: str) -> bool:
    status = "PASS" if passed else "WARN"
    print(f"[{status}] {name}: {detail}")
    return passed


def check_legacy_rework_or_mismatch(f_rows: list[dict]) -> bool:
    rework = mean_by(f_rows, "project_type", "rework_rate")
    mismatch = mean_by(f_rows, "project_type", "domain_mismatch_count")
    legacy_rework, maintenance_rework = metric_pair(
        rework,
        "legacy_migration",
        "maintenance_enhancement",
    )
    legacy_mismatch, maintenance_mismatch = metric_pair(
        mismatch,
        "legacy_migration",
        "maintenance_enhancement",
    )
    passed = (
        legacy_rework is not None and maintenance_rework is not None and
        legacy_rework > maintenance_rework
    ) or (
        legacy_mismatch is not None and maintenance_mismatch is not None and
        legacy_mismatch > maintenance_mismatch
    )
    return print_check(
        "legacy_migration rework/domain mismatch pressure",
        passed,
        (
            f"rework_rate legacy={fmt(legacy_rework)} vs maintenance={fmt(maintenance_rework)}, "
            f"domain_mismatch_count legacy={fmt(legacy_mismatch)} vs maintenance={fmt(maintenance_mismatch)}"
        ),
    )


def check_deadline_pressure(f_rows: list[dict]) -> bool:
    backlog = mean_by(f_rows, "project_type", "remaining_backlog")
    energy = mean_by(f_rows, "project_type", "avg_energy")
    deadline_backlog, maintenance_backlog = metric_pair(
        backlog,
        "deadline_driven",
        "maintenance_enhancement",
    )
    deadline_energy, maintenance_energy = metric_pair(
        energy,
        "deadline_driven",
        "maintenance_enhancement",
    )
    passed = (
        deadline_backlog is not None and maintenance_backlog is not None and
        deadline_backlog > maintenance_backlog
    ) or (
        deadline_energy is not None and maintenance_energy is not None and
        deadline_energy < maintenance_energy
    )
    return print_check(
        "deadline_driven backlog/energy pressure",
        passed,
        (
            f"remaining_backlog deadline={fmt(deadline_backlog)} vs maintenance={fmt(maintenance_backlog)}, "
            f"avg_energy deadline={fmt(deadline_energy)} vs maintenance={fmt(maintenance_energy)}"
        ),
    )


def check_strong_pm_scope_control(g_rows: list[dict]) -> bool:
    prevented = mean_by(g_rows, "pm_profile", "scope_changes_prevented")
    strong, weak = metric_pair(prevented, "strong_pm", "weak_pm")
    passed = strong is not None and weak is not None and strong > weak
    return print_check(
        "strong_pm scope control",
        passed,
        f"scope_changes_prevented strong_pm={fmt(strong)} vs weak_pm={fmt(weak)}",
    )


def check_junior_help_load(f_rows: list[dict]) -> bool:
    help_requests = mean_by(f_rows, "team_composition", "help_requests_total")
    junior, senior = metric_pair(help_requests, "junior_heavy", "senior_heavy")
    passed = junior is not None and senior is not None and junior > senior
    return print_check(
        "junior_heavy help request load",
        passed,
        f"help_requests_total junior_heavy={fmt(junior)} vs senior_heavy={fmt(senior)}",
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Run lightweight Scenario F/G sanity checks.")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--sprints", type=int, default=DEFAULT_SPRINTS)
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEED_START)
    parser.add_argument("--num-developers", type=int, default=DEFAULT_NUM_DEVELOPERS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(
        "Running sanity scenarios "
        f"(F/G, runs={args.runs}, sprints={args.sprints}, seed_start={args.seed_start})..."
    )
    f_rows = run_scenario("F", args.runs, args.sprints, args.seed_start, args.num_developers)
    g_rows = run_scenario(
        "G",
        args.runs,
        args.sprints,
        args.seed_start + args.runs * 100,
        args.num_developers,
    )
    print(f"Collected {len(f_rows)} Scenario F rows and {len(g_rows)} Scenario G rows.")

    checks = [
        check_legacy_rework_or_mismatch(f_rows),
        check_deadline_pressure(f_rows),
        check_strong_pm_scope_control(g_rows),
        check_junior_help_load(f_rows),
    ]
    pass_count = sum(1 for passed in checks if passed)
    warn_count = len(checks) - pass_count
    print(f"Sanity check complete: {pass_count} PASS, {warn_count} WARN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
