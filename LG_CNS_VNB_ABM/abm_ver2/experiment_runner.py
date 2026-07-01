#!/usr/bin/env python3
import argparse
import csv
import statistics
from pathlib import Path

from model import PM_PROFILES
from simulate import run_simulation


METRIC_COLUMNS = [
    "PRs per Engineer",
    "Lead Time (steps)",
    "Deployment Frequency",
    "Change Failure Rate (%)",
    "Recovery Time (steps)",
    "% Time on New Capabilities",
]

PROJECT_TYPES = [
    "new_build",
    "maintenance_enhancement",
    "legacy_migration",
    "deadline_driven",
    "quality_critical",
]

TEAM_COMPOSITIONS = ["junior_heavy", "balanced", "senior_heavy"]
SCENARIO_H_PROJECT_TYPES = ["new_build", "legacy_migration", "deadline_driven"]
SCENARIO_H_MENTORING_INTENSITIES = [0.2, 0.5, 0.8]
SCENARIO_I_PROJECT_TYPES = ["new_build", "deadline_driven", "quality_critical"]
SCENARIO_I_REQUIREMENT_VOLATILITY = [0.2, 0.5, 0.8]
SCENARIO_I_PM_PROFILES = ["weak_pm", "requirement_focused_pm", "strong_pm"]

INTERNAL_METRIC_COLUMNS = [
    "avg_energy",
    "avg_motivation",
    "min_energy",
    "avg_knowledge",
    "avg_team_domain_knowledge",
    "min_team_domain_knowledge",
    "domain_coverage",
    "help_requests_total",
    "help_requests_resolved",
    "help_request_resolution_rate",
    "mentoring_load_total",
    "avg_knowledge_gain_from_help",
    "helper_interruptions",
    "staffing_cost",
    "completed_tasks_per_cost",
    "PRs_per_cost",
    "interaction_event_count",
    "interaction_load",
    "help_request_count",
    "help_success_count",
    "help_resolution_rate",
    "help_network_density",
    "senior_bottleneck_index",
    "review_assignment_count",
    "review_concentration_index",
    "senior_review_load_per_senior",
    "senior_interaction_load_per_senior",
    "senior_overload_risk",
    "incident_interrupt_count",
    "incident_interruptions",
    "pm_intervention_count",
    "pm_leverage_index",
    "rework_count",
    "rework_rate",
    "avg_rework_per_completed_task",
    "junior_count",
    "middle_count",
    "senior_count",
    "junior_avg_knowledge",
    "senior_mentoring_load",
    "senior_mentoring_load_per_senior",
    "junior_help_requests",
    "allocation_match_score",
    "domain_mismatch_count",
    "bottlenecks_detected",
    "bottleneck_interventions",
    "reassignments",
    "clarification_events",
    "scope_changes",
    "scope_changes_prevented",
    "pm_capacity_used",
    "effective_requirement_clarity",
    "attrition_count",
    "coaching_count",
    "remaining_backlog",
    "completed_tasks",
    "active_developers",
    "low_energy_count",
]

PARAM_COLUMNS = [
    "project_type",
    "meeting_load",
    "requirement_clarity",
    "review_strictness",
    "codebase_stability",
    "sprint_backlog_size",
    "requirement_volatility",
    "team_awareness",
    "team_composition",
    "mentoring_intensity",
    "pm_profile",
    "allocation_skill",
    "bottleneck_detection",
    "requirement_coordination",
    "scope_control",
]

RESULT_COLUMNS = [
    "scenario_id",
    "condition_id",
    "run_id",
    "seed",
    "num_sprints",
] + PARAM_COLUMNS + METRIC_COLUMNS + INTERNAL_METRIC_COLUMNS


SUMMARY_BASE_COLUMNS = [
    "scenario_id",
    "condition_id",
    "runs",
    "num_sprints",
] + PARAM_COLUMNS


def summary_metric_column(metric, stat):
    return f"{metric} {stat}"


def summary_metric_columns(metric):
    return [
        summary_metric_column(metric, "mean"),
        summary_metric_column(metric, "std"),
    ]


def summary_fieldnames():
    columns = list(SUMMARY_BASE_COLUMNS)
    for metric in METRIC_COLUMNS + INTERNAL_METRIC_COLUMNS:
        columns.extend(summary_metric_columns(metric))
    return columns


def normalize_summary_column(column):
    for metric in METRIC_COLUMNS + INTERNAL_METRIC_COLUMNS:
        for canonical in summary_metric_columns(metric):
            stat = canonical.rsplit(" ", 1)[1]
            if column in (canonical, f"{metric}{stat}"):
                return canonical
    return column


def normalize_summary_row(row):
    return {
        normalize_summary_column(key): value
        for key, value in row.items()
    }


def summary_row_values(row, fieldnames):
    normalized_row = normalize_summary_row(row)
    return [normalized_row.get(fieldname, "") for fieldname in fieldnames]


def scenario_a_conditions():
    conditions = []
    condition_index = 1
    for requirement_clarity in [0.4, 0.8]:
        for meeting_load in [30, 60, 120, 180]:
            conditions.append({
                "scenario_id": "A",
                "condition_id": f"A{condition_index}",
                "meeting_load": meeting_load,
                "requirement_clarity": requirement_clarity,
            })
            condition_index += 1
    return conditions


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


def scenario_c_conditions():
    conditions = []
    condition_index = 1
    for team_awareness in [0.4, 0.8]:
        for sprint_backlog_size in [10, 20, 30, 40, 50]:
            conditions.append({
                "scenario_id": "C",
                "condition_id": f"C{condition_index}",
                "sprint_backlog_size": sprint_backlog_size,
                "team_awareness": team_awareness,
                "distribution_overrides": {
                    "pl.team_awareness": {
                        "type": "constant",
                        "value": team_awareness,
                    },
                },
            })
            condition_index += 1
    return conditions


def scenario_d_conditions():
    conditions = []
    condition_index = 1
    for team_composition in TEAM_COMPOSITIONS:
        for mentoring_intensity in [0.3, 0.8]:
            conditions.append({
                "scenario_id": "D",
                "condition_id": f"D{condition_index}",
                "team_composition": team_composition,
                "mentoring_intensity": mentoring_intensity,
            })
            condition_index += 1
    return conditions


def scenario_e_conditions():
    conditions = []
    for condition_index, pm_profile in enumerate(PM_PROFILES, start=1):
        conditions.append({
            "scenario_id": "E",
            "condition_id": f"E{condition_index}",
            "pm_profile": pm_profile,
        })
    return conditions


def scenario_f_conditions():
    conditions = []
    condition_index = 1
    for project_type in PROJECT_TYPES:
        for team_composition in TEAM_COMPOSITIONS:
            conditions.append({
                "scenario_id": "F",
                "condition_id": f"F{condition_index}",
                "project_type": project_type,
                "team_composition": team_composition,
            })
            condition_index += 1
    return conditions


def scenario_g_conditions():
    conditions = []
    condition_index = 1
    for project_type in PROJECT_TYPES:
        for pm_profile in PM_PROFILES:
            conditions.append({
                "scenario_id": "G",
                "condition_id": f"G{condition_index}",
                "project_type": project_type,
                "pm_profile": pm_profile,
            })
            condition_index += 1
    return conditions


def scenario_h_conditions():
    conditions = []
    condition_index = 1
    for project_type in SCENARIO_H_PROJECT_TYPES:
        for team_composition in TEAM_COMPOSITIONS:
            for mentoring_intensity in SCENARIO_H_MENTORING_INTENSITIES:
                conditions.append({
                    "scenario_id": "H",
                    "condition_id": f"H{condition_index}",
                    "project_type": project_type,
                    "team_composition": team_composition,
                    "mentoring_intensity": mentoring_intensity,
                })
                condition_index += 1
    return conditions


def scenario_i_conditions():
    conditions = []
    condition_index = 1
    for project_type in SCENARIO_I_PROJECT_TYPES:
        for requirement_volatility in SCENARIO_I_REQUIREMENT_VOLATILITY:
            for pm_profile in SCENARIO_I_PM_PROFILES:
                conditions.append({
                    "scenario_id": "I",
                    "condition_id": f"I{condition_index}",
                    "project_type": project_type,
                    "requirement_volatility": requirement_volatility,
                    "pm_profile": pm_profile,
                })
                condition_index += 1
    return conditions


def condition_display_params(condition):
    display_params = dict(condition)
    pm_profile = condition.get("pm_profile")
    if pm_profile in PM_PROFILES:
        for key, value in PM_PROFILES[pm_profile].items():
            display_params.setdefault(key, value)
    return display_params


def get_conditions(scenario_id):
    if scenario_id == "A":
        return scenario_a_conditions()
    if scenario_id == "B":
        return scenario_b_conditions()
    if scenario_id == "C":
        return scenario_c_conditions()
    if scenario_id == "D":
        return scenario_d_conditions()
    if scenario_id == "E":
        return scenario_e_conditions()
    if scenario_id == "F":
        return scenario_f_conditions()
    if scenario_id == "G":
        return scenario_g_conditions()
    if scenario_id == "H":
        return scenario_h_conditions()
    if scenario_id == "I":
        return scenario_i_conditions()
    raise ValueError(f"Unsupported scenario: {scenario_id}")


def run_condition(condition, runs, num_sprints, seed_start, num_developers):
    rows = []
    display_params = condition_display_params(condition)
    for run_index in range(runs):
        seed = seed_start + run_index
        params = {
            "num_developers": num_developers,
            "num_sprints": num_sprints,
            "seed": seed,
        }
        for column in PARAM_COLUMNS:
            if column != "team_awareness" and column in condition:
                params[column] = condition[column]
        if "distribution_overrides" in condition:
            params["distribution_overrides"] = condition["distribution_overrides"]

        result = run_simulation(params)
        prism = result.get("prism", {})
        internal_metrics = result.get("internal_metrics", {})

        row = {
            "scenario_id": condition["scenario_id"],
            "condition_id": condition["condition_id"],
            "run_id": run_index + 1,
            "seed": seed,
            "num_sprints": num_sprints,
        }
        for column in PARAM_COLUMNS:
            row[column] = display_params.get(column, "")
        for metric in METRIC_COLUMNS:
            row[metric] = prism.get(metric, "")
        for metric in INTERNAL_METRIC_COLUMNS:
            row[metric] = internal_metrics.get(metric, "")
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
        }
        for column in PARAM_COLUMNS:
            summary[column] = first.get(column, "")

        for metric in METRIC_COLUMNS + INTERNAL_METRIC_COLUMNS:
            values = [float(row[metric]) for row in condition_rows if row[metric] != ""]
            summary[summary_metric_column(metric, "mean")] = statistics.mean(values) if values else ""
            summary[summary_metric_column(metric, "std")] = statistics.stdev(values) if len(values) > 1 else 0.0
        summary_rows.append(summary)
    return summary_rows


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(path, rows):
    fieldnames = summary_fieldnames()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fieldnames)
        for row in rows:
            writer.writerow(summary_row_values(row, fieldnames))


def parse_args():
    parser = argparse.ArgumentParser(description="Run scenario-based ABM experiments.")
    parser.add_argument("--scenario", default="B", choices=["A", "B", "C", "D", "E", "F", "G", "H", "I"])
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--sprints", type=int, default=6)
    parser.add_argument("--seed-start", type=int, default=1000)
    parser.add_argument("--num-developers", type=int, default=9)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    return parser.parse_args()


def main():
    args = parse_args()
    rows = []
    for condition in get_conditions(args.scenario):
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

    write_csv(args.output_dir / "experiment_results.csv", rows, RESULT_COLUMNS)
    write_summary_csv(args.output_dir / "experiment_summary.csv", summary_rows)

    print(f"Wrote {len(rows)} run-level rows to {args.output_dir / 'experiment_results.csv'}")
    print(f"Wrote {len(summary_rows)} summary rows to {args.output_dir / 'experiment_summary.csv'}")


if __name__ == "__main__":
    main()
