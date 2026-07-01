#!/usr/bin/env python3
"""Create report-ready CSV tables and figures from final experiment summaries."""
import csv
import math
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FINAL_DIR = BASE_DIR / "outputs" / "final"
TABLE_DIR = FINAL_DIR / "report_tables"
FIGURE_DIR = FINAL_DIR / "figures"

SCENARIO_SUMMARIES = {
    "A": FINAL_DIR / "scenario_A_summary.csv",
    "B": FINAL_DIR / "scenario_B_summary.csv",
    "C": FINAL_DIR / "scenario_C_summary.csv",
    "D": FINAL_DIR / "scenario_D_summary.csv",
    "E": FINAL_DIR / "scenario_E_summary.csv",
}

TEAM_COMPOSITION_ORDER = ["junior_heavy", "balanced", "senior_heavy"]
PM_PROFILE_ORDER = [
    "weak_pm",
    "allocation_focused_pm",
    "bottleneck_focused_pm",
    "requirement_focused_pm",
    "strong_pm",
]

SCENARIO_D_REPORT_COLUMNS = [
    "condition_id",
    "team_composition",
    "mentoring_intensity",
    "PRs per Engineer mean",
    "Lead Time (steps) mean",
    "Change Failure Rate (%) mean",
    "avg_energy mean",
    "avg_knowledge mean",
    "help_requests_total mean",
    "help_requests_resolved mean",
    "help_request_resolution_rate mean",
    "mentoring_load_total mean",
    "avg_knowledge_gain_from_help mean",
    "helper_interruptions mean",
    "junior_avg_knowledge mean",
    "senior_mentoring_load mean",
    "junior_help_requests mean",
]

SCENARIO_D_IMPACT_METRICS = [
    "PRs per Engineer mean",
    "help_request_resolution_rate mean",
    "mentoring_load_total mean",
    "avg_knowledge_gain_from_help mean",
    "helper_interruptions mean",
    "junior_help_requests mean",
]

SCENARIO_D_COMPARISONS = [
    ("D1", "D2", "junior_heavy mentoring intensity increase"),
    ("D3", "D4", "balanced mentoring intensity increase"),
    ("D5", "D6", "senior_heavy mentoring intensity increase"),
    ("D1", "D5", "low mentoring junior_heavy vs senior_heavy"),
    ("D2", "D6", "high mentoring junior_heavy vs senior_heavy"),
]

SCENARIO_E_REPORT_COLUMNS = [
    "condition_id",
    "pm_profile",
    "allocation_skill",
    "bottleneck_detection",
    "requirement_coordination",
    "PRs per Engineer mean",
    "Lead Time (steps) mean",
    "Change Failure Rate (%) mean",
    "avg_energy mean",
    "help_requests_total mean",
    "help_request_resolution_rate mean",
    "mentoring_load_total mean",
    "helper_interruptions mean",
    "allocation_match_score mean",
    "domain_mismatch_count mean",
    "bottlenecks_detected mean",
    "bottleneck_interventions mean",
    "reassignments mean",
    "clarification_events mean",
    "effective_requirement_clarity mean",
]

SCENARIO_E_IMPACT_METRICS = [
    "PRs per Engineer mean",
    "avg_energy mean",
    "Change Failure Rate (%) mean",
    "allocation_match_score mean",
    "domain_mismatch_count mean",
    "bottleneck_interventions mean",
    "reassignments mean",
    "effective_requirement_clarity mean",
    "clarification_events mean",
]

SCENARIO_E_COMPARISONS = [
    ("E1", "E2", "weak_pm 대비 allocation_focused_pm"),
    ("E1", "E3", "weak_pm 대비 bottleneck_focused_pm"),
    ("E1", "E4", "weak_pm 대비 requirement_focused_pm"),
    ("E1", "E5", "weak_pm 대비 strong_pm"),
]

SCENARIO_E_INTERPRETATIONS = {
    ("E1", "E2"): {
        "allocation_match_score mean": "업무 배분 역량 향상에 따라 domain match 개선",
        "domain_mismatch_count mean": "업무 배분 역량 향상에 따라 domain mismatch 감소",
        "PRs per Engineer mean": "업무 배분 개선이 개인 생산성에 미치는 영향",
        "Lead Time (steps) mean": "업무 배분 개선이 리드타임에 미치는 영향",
    },
    ("E1", "E3"): {
        "avg_energy mean": "병목 감지 역량 향상에 따라 평균 에너지 개선",
        "bottleneck_interventions mean": "병목 감지 역량 향상에 따라 병목 개입 증가",
        "reassignments mean": "병목 감지 역량 향상에 따라 재배정 증가",
    },
    ("E1", "E4"): {
        "Change Failure Rate (%) mean": "요구사항 조율 역량 향상에 따라 실패율 감소",
        "effective_requirement_clarity mean": "요구사항 조율 역량 향상에 따라 effective clarity 증가",
        "clarification_events mean": "요구사항 조율 이벤트가 품질 개선 비용으로 발생",
    },
    ("E1", "E5"): {
        "avg_energy mean": "strong PM은 weak PM 대비 에너지 지표 개선",
        "Change Failure Rate (%) mean": "strong PM은 weak PM 대비 품질 지표 개선",
        "domain_mismatch_count mean": "strong PM은 weak PM 대비 domain mismatch 감소",
        "effective_requirement_clarity mean": "strong PM은 weak PM 대비 요구사항 명확도 개선",
    },
}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Required final summary CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value) -> str:
    number = to_float(value)
    if number is None or not math.isfinite(number):
        return ""
    return f"{number:.3f}"


def format_label(value) -> str:
    number = to_float(value)
    if number is None:
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.3f}".rstrip("0").rstrip(".")


def pct_change(value, baseline):
    value_number = to_float(value)
    baseline_number = to_float(baseline)
    if value_number is None or baseline_number in (None, 0):
        return None
    return (value_number - baseline_number) / baseline_number * 100.0


def group_by(rows: list[dict], key: str) -> dict:
    grouped = {}
    for row in rows:
        grouped.setdefault(row.get(key, ""), []).append(row)
    return grouped


def condition_sort_key(row: dict) -> tuple[str, int]:
    condition_id = row.get("condition_id", "")
    prefix = condition_id[:1]
    try:
        index = int(condition_id[1:])
    except ValueError:
        index = 0
    return prefix, index


def sort_rows_numeric(rows: list[dict], key: str) -> list[dict]:
    return sorted(rows, key=lambda row: (to_float(row.get(key)) is None, to_float(row.get(key)) or 0))


def team_composition_index(value: str) -> int:
    try:
        return TEAM_COMPOSITION_ORDER.index(value)
    except ValueError:
        return len(TEAM_COMPOSITION_ORDER)


def sort_scenario_d_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            team_composition_index(row.get("team_composition", "")),
            to_float(row.get("mentoring_intensity")) or 0,
            condition_sort_key(row),
        ),
    )


def pm_profile_index(value: str) -> int:
    try:
        return PM_PROFILE_ORDER.index(value)
    except ValueError:
        return len(PM_PROFILE_ORDER)


def sort_scenario_e_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            pm_profile_index(row.get("pm_profile", "")),
            condition_sort_key(row),
        ),
    )


def rows_by_condition(rows: list[dict]) -> dict:
    return {row.get("condition_id"): row for row in rows}


def copy_formatted(row: dict, columns: list[str]) -> dict:
    formatted = {}
    for column in columns:
        if column == "condition_id":
            formatted[column] = row.get(column, "")
        else:
            formatted[column] = format_number(row.get(column))
    return formatted


def copy_scenario_d_report_row(row: dict) -> dict:
    formatted = {}
    for column in SCENARIO_D_REPORT_COLUMNS:
        if column in {"condition_id", "team_composition"}:
            formatted[column] = row.get(column, "")
        elif column == "mentoring_intensity":
            formatted[column] = format_label(row.get(column))
        else:
            formatted[column] = format_number(row.get(column))
    return formatted


def copy_scenario_e_report_row(row: dict) -> dict:
    formatted = {}
    for column in SCENARIO_E_REPORT_COLUMNS:
        if column in {"condition_id", "pm_profile"}:
            formatted[column] = row.get(column, "")
        elif column in {
            "allocation_skill",
            "bottleneck_detection",
            "requirement_coordination",
        }:
            formatted[column] = format_label(row.get(column))
        else:
            formatted[column] = format_number(row.get(column))
    return formatted


def add_pct_columns(output_row: dict, row: dict, baseline: dict, specs: list[tuple[str, str]]) -> None:
    for output_column, metric_column in specs:
        output_row[output_column] = format_number(
            pct_change(row.get(metric_column), baseline.get(metric_column))
        )


def build_scenario_a_table(rows: list[dict]) -> tuple[list[dict], list[str]]:
    columns = [
        "condition_id",
        "meeting_load",
        "requirement_clarity",
        "PRs per Engineer mean",
        "Change Failure Rate (%) mean",
        "avg_energy mean",
        "min_energy mean",
        "coaching_count mean",
        "active_developers mean",
        "attrition_count mean",
    ]
    pct_columns = [
        "prs_change_pct_vs_A2",
        "energy_change_pct_vs_A2",
        "cfr_change_pct_vs_A2",
        "coaching_change_pct_vs_A2",
    ]
    baseline = rows_by_condition(rows)["A2"]
    output_rows = []
    for row in sorted(rows, key=condition_sort_key):
        output_row = copy_formatted(row, columns)
        add_pct_columns(
            output_row,
            row,
            baseline,
            [
                ("prs_change_pct_vs_A2", "PRs per Engineer mean"),
                ("energy_change_pct_vs_A2", "avg_energy mean"),
                ("cfr_change_pct_vs_A2", "Change Failure Rate (%) mean"),
                ("coaching_change_pct_vs_A2", "coaching_count mean"),
            ],
        )
        output_rows.append(output_row)
    return output_rows, columns + pct_columns


def baseline_for_numeric_group(row: dict, group_column: str, baseline_map: dict[float, dict]) -> dict:
    group_value = to_float(row.get(group_column))
    for expected, baseline in baseline_map.items():
        if group_value is not None and abs(group_value - expected) < 1e-9:
            return baseline
    raise ValueError(f"No baseline configured for {group_column}={row.get(group_column)}")


def build_scenario_b_table(rows: list[dict]) -> tuple[list[dict], list[str]]:
    columns = [
        "condition_id",
        "review_strictness",
        "codebase_stability",
        "PRs per Engineer mean",
        "Lead Time (steps) mean",
        "Deployment Frequency mean",
        "Change Failure Rate (%) mean",
        "Recovery Time (steps) mean",
        "avg_energy mean",
        "attrition_count mean",
    ]
    pct_columns = [
        "cfr_change_pct_vs_baseline",
        "lead_time_change_pct_vs_baseline",
    ]
    by_condition = rows_by_condition(rows)
    baseline_map = {0.4: by_condition["B1"], 0.8: by_condition["B5"]}
    output_rows = []
    for row in sorted(rows, key=condition_sort_key):
        baseline = baseline_for_numeric_group(row, "codebase_stability", baseline_map)
        output_row = copy_formatted(row, columns)
        add_pct_columns(
            output_row,
            row,
            baseline,
            [
                ("cfr_change_pct_vs_baseline", "Change Failure Rate (%) mean"),
                ("lead_time_change_pct_vs_baseline", "Lead Time (steps) mean"),
            ],
        )
        output_rows.append(output_row)
    return output_rows, columns + pct_columns


def build_scenario_c_table(rows: list[dict]) -> tuple[list[dict], list[str]]:
    columns = [
        "condition_id",
        "sprint_backlog_size",
        "team_awareness",
        "PRs per Engineer mean",
        "Lead Time (steps) mean",
        "Deployment Frequency mean",
        "avg_energy mean",
        "min_energy mean",
        "attrition_count mean",
        "coaching_count mean",
        "remaining_backlog mean",
        "active_developers mean",
    ]
    pct_columns = [
        "prs_change_pct_vs_baseline",
        "energy_change_pct_vs_baseline",
        "remaining_backlog_change_pct_vs_baseline",
    ]
    by_condition = rows_by_condition(rows)
    baseline_map = {0.4: by_condition["C1"], 0.8: by_condition["C6"]}
    output_rows = []
    for row in sorted(rows, key=condition_sort_key):
        baseline = baseline_for_numeric_group(row, "team_awareness", baseline_map)
        output_row = copy_formatted(row, columns)
        add_pct_columns(
            output_row,
            row,
            baseline,
            [
                ("prs_change_pct_vs_baseline", "PRs per Engineer mean"),
                ("energy_change_pct_vs_baseline", "avg_energy mean"),
                ("remaining_backlog_change_pct_vs_baseline", "remaining_backlog mean"),
            ],
        )
        output_rows.append(output_row)
    return output_rows, columns + pct_columns


def build_scenario_d_table(rows: list[dict]) -> tuple[list[dict], list[str]]:
    output_rows = [
        copy_scenario_d_report_row(row)
        for row in sort_scenario_d_rows(rows)
    ]
    return output_rows, SCENARIO_D_REPORT_COLUMNS


def build_scenario_e_table(rows: list[dict]) -> tuple[list[dict], list[str]]:
    output_rows = [
        copy_scenario_e_report_row(row)
        for row in sort_scenario_e_rows(rows)
    ]
    return output_rows, SCENARIO_E_REPORT_COLUMNS


def add_impact_row(
    rows: list[dict],
    scenario_id: str,
    summary_rows: list[dict],
    baseline_condition: str,
    target_condition: str,
    key_metric: str,
    interpretation: str,
) -> None:
    by_condition = rows_by_condition(summary_rows)
    baseline = by_condition[baseline_condition]
    target = by_condition[target_condition]
    baseline_value = to_float(baseline.get(key_metric))
    target_value = to_float(target.get(key_metric))
    rows.append(
        {
            "scenario_id": scenario_id,
            "comparison": f"{baseline_condition}->{target_condition}",
            "key_metric": key_metric,
            "baseline_condition": baseline_condition,
            "target_condition": target_condition,
            "baseline_value": format_number(baseline_value),
            "target_value": format_number(target_value),
            "change_pct": format_number(pct_change(target_value, baseline_value)),
            "interpretation": interpretation,
        }
    )


def build_scenario_d_impact_summary(summary_rows: list[dict]) -> tuple[list[dict], list[str]]:
    rows = []
    by_condition = rows_by_condition(summary_rows)
    for baseline_condition, target_condition, comparison_label in SCENARIO_D_COMPARISONS:
        baseline = by_condition[baseline_condition]
        target = by_condition[target_condition]
        for metric in SCENARIO_D_IMPACT_METRICS:
            baseline_value = to_float(baseline.get(metric))
            target_value = to_float(target.get(metric))
            rows.append(
                {
                    "scenario_id": "D",
                    "comparison": f"{baseline_condition}->{target_condition}",
                    "comparison_label": comparison_label,
                    "key_metric": metric,
                    "baseline_condition": baseline_condition,
                    "target_condition": target_condition,
                    "baseline_team_composition": baseline.get("team_composition", ""),
                    "target_team_composition": target.get("team_composition", ""),
                    "baseline_mentoring_intensity": format_label(baseline.get("mentoring_intensity")),
                    "target_mentoring_intensity": format_label(target.get("mentoring_intensity")),
                    "baseline_value": format_number(baseline_value),
                    "target_value": format_number(target_value),
                    "change_pct": format_number(pct_change(target_value, baseline_value)),
                }
            )
    fieldnames = [
        "scenario_id",
        "comparison",
        "comparison_label",
        "key_metric",
        "baseline_condition",
        "target_condition",
        "baseline_team_composition",
        "target_team_composition",
        "baseline_mentoring_intensity",
        "target_mentoring_intensity",
        "baseline_value",
        "target_value",
        "change_pct",
    ]
    return rows, fieldnames


def scenario_e_interpretation(
    baseline_condition: str,
    target_condition: str,
    metric: str,
) -> str:
    comparison_map = SCENARIO_E_INTERPRETATIONS.get(
        (baseline_condition, target_condition),
        {},
    )
    if metric in comparison_map:
        return comparison_map[metric]

    defaults = {
        "PRs per Engineer mean": "PM 역량 변화가 개인 생산성에 미치는 영향",
        "avg_energy mean": "PM 역량 변화가 개발자 에너지에 미치는 영향",
        "Change Failure Rate (%) mean": "PM 역량 변화가 품질 지표에 미치는 영향",
        "allocation_match_score mean": "업무 배분 적합도 변화",
        "domain_mismatch_count mean": "domain mismatch 변화",
        "bottleneck_interventions mean": "병목 개입 빈도 변화",
        "reassignments mean": "병목 완화를 위한 재배정 변화",
        "effective_requirement_clarity mean": "요구사항 명확도 변화",
        "clarification_events mean": "요구사항 조율 이벤트 변화",
    }
    return defaults.get(metric, "PM 역량 변화에 따른 지표 변화")


def build_scenario_e_impact_summary(summary_rows: list[dict]) -> tuple[list[dict], list[str]]:
    rows = []
    by_condition = rows_by_condition(summary_rows)
    for baseline_condition, target_condition, comparison_label in SCENARIO_E_COMPARISONS:
        baseline = by_condition[baseline_condition]
        target = by_condition[target_condition]
        for metric in SCENARIO_E_IMPACT_METRICS:
            baseline_value = to_float(baseline.get(metric))
            target_value = to_float(target.get(metric))
            rows.append(
                {
                    "scenario": "E",
                    "comparison": comparison_label,
                    "metric": metric,
                    "from_condition": baseline_condition,
                    "to_condition": target_condition,
                    "from_value": format_number(baseline_value),
                    "to_value": format_number(target_value),
                    "pct_change": format_number(pct_change(target_value, baseline_value)),
                    "interpretation": scenario_e_interpretation(
                        baseline_condition,
                        target_condition,
                        metric,
                    ),
                }
            )
    fieldnames = [
        "scenario",
        "comparison",
        "metric",
        "from_condition",
        "to_condition",
        "from_value",
        "to_value",
        "pct_change",
        "interpretation",
    ]
    return rows, fieldnames


def build_impact_summary(all_rows: dict[str, list[dict]]) -> tuple[list[dict], list[str]]:
    rows = []
    add_impact_row(rows, "A", all_rows["A"], "A2", "A4", "PRs per Engineer mean", "회의 부하 증가에 따라 개인 생산성이 감소")
    add_impact_row(rows, "A", all_rows["A"], "A2", "A4", "avg_energy mean", "회의 부하 증가에 따라 평균 에너지가 감소")
    add_impact_row(rows, "A", all_rows["A"], "A2", "A4", "coaching_count mean", "회의 부하 증가에 따라 코칭 필요가 증가")
    add_impact_row(rows, "A", all_rows["A"], "A2", "A6", "Change Failure Rate (%) mean", "요구사항 명확도 향상에 따라 실패율 감소")
    add_impact_row(rows, "B", all_rows["B"], "B1", "B4", "Change Failure Rate (%) mean", "리뷰 엄격도 증가에 따라 실패율 감소")
    add_impact_row(rows, "B", all_rows["B"], "B1", "B4", "Lead Time (steps) mean", "리뷰 엄격도 증가에 따라 리드타임이 변화")
    add_impact_row(rows, "B", all_rows["B"], "B5", "B8", "Change Failure Rate (%) mean", "안정적 코드베이스에서도 리뷰 엄격도가 실패율을 낮춤")
    add_impact_row(rows, "B", all_rows["B"], "B5", "B8", "Lead Time (steps) mean", "안정적 코드베이스에서 리뷰 비용이 리드타임에 반영")
    add_impact_row(rows, "C", all_rows["C"], "C1", "C5", "PRs per Engineer mean", "백로그 증가에 따라 개인 생산성이 변화")
    add_impact_row(rows, "C", all_rows["C"], "C1", "C5", "avg_energy mean", "백로그 증가에 따라 평균 에너지가 감소")
    add_impact_row(rows, "C", all_rows["C"], "C1", "C5", "remaining_backlog mean", "백로그 증가에 따라 미처리 업무가 누적")
    add_impact_row(rows, "C", all_rows["C"], "C6", "C10", "avg_energy mean", "높은 팀 인지 조건에서도 백로그 압박이 에너지에 반영")
    add_impact_row(rows, "C", all_rows["C"], "C6", "C10", "remaining_backlog mean", "높은 팀 인지 조건에서도 미처리 업무가 증가")
    fieldnames = [
        "scenario_id",
        "comparison",
        "key_metric",
        "baseline_condition",
        "target_condition",
        "baseline_value",
        "target_value",
        "change_pct",
        "interpretation",
    ]
    return rows, fieldnames


def get_pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def save_line_chart(rows, x_key, y_key, group_key, title, xlabel, ylabel, path):
    plt = get_pyplot()
    fig, ax = plt.subplots()
    for group_value, group_rows in sorted(group_by(rows, group_key).items(), key=lambda item: to_float(item[0]) or 0):
        sorted_rows = sort_rows_numeric(group_rows, x_key)
        xs = [to_float(row.get(x_key)) for row in sorted_rows]
        ys = [to_float(row.get(y_key)) for row in sorted_rows]
        ax.plot(xs, ys, marker="o", label=f"{group_key}={format_label(group_value)}")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True)
    ax.legend()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_team_composition_line_chart(rows, y_key, title, ylabel, path):
    plt = get_pyplot()
    fig, ax = plt.subplots(figsize=(8, 5))
    x_positions = list(range(len(TEAM_COMPOSITION_ORDER)))
    grouped = group_by(rows, "mentoring_intensity")
    for intensity, group_rows in sorted(grouped.items(), key=lambda item: to_float(item[0]) or 0):
        by_composition = {
            row.get("team_composition", ""): row
            for row in group_rows
        }
        ys = []
        for composition in TEAM_COMPOSITION_ORDER:
            value = to_float(by_composition.get(composition, {}).get(y_key))
            ys.append(value if value is not None else math.nan)
        ax.plot(
            x_positions,
            ys,
            marker="o",
            label=f"mentoring_intensity={format_label(intensity)}",
        )
    ax.set_title(title)
    ax.set_xlabel("Team Composition")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(TEAM_COMPOSITION_ORDER)
    ax.grid(True, axis="y")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def scenario_e_plot_rows(rows: list[dict]) -> list[dict]:
    return sort_scenario_e_rows(rows)


def scenario_e_labels(rows: list[dict]) -> list[str]:
    return [row.get("pm_profile", "") for row in scenario_e_plot_rows(rows)]


def save_pm_profile_bar_chart(rows, y_key, title, ylabel, path):
    plt = get_pyplot()
    plot_rows = scenario_e_plot_rows(rows)
    labels = [row.get("pm_profile", "") for row in plot_rows]
    values = [to_float(row.get(y_key)) or 0.0 for row in plot_rows]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(labels, values)
    ax.set_title(title)
    ax.set_xlabel("PM Profile")
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y")
    ax.tick_params(axis="x", labelrotation=30)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_pm_profile_grouped_bar_chart(rows, series_specs, title, ylabel, path):
    plt = get_pyplot()
    plot_rows = scenario_e_plot_rows(rows)
    labels = [row.get("pm_profile", "") for row in plot_rows]
    x_positions = list(range(len(labels)))
    series_count = max(len(series_specs), 1)
    bar_width = min(0.8 / series_count, 0.35)
    start_offset = -bar_width * (series_count - 1) / 2

    fig, ax = plt.subplots(figsize=(9, 5))
    for series_index, (metric, label) in enumerate(series_specs):
        offset = start_offset + series_index * bar_width
        values = [to_float(row.get(metric)) or 0.0 for row in plot_rows]
        xs = [position + offset for position in x_positions]
        ax.bar(xs, values, width=bar_width, label=label)

    ax.set_title(title)
    ax.set_xlabel("PM Profile")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.grid(True, axis="y")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_pm_impact_summary_chart(rows, path):
    plt = get_pyplot()
    plot_rows = scenario_e_plot_rows(rows)
    labels = [row.get("pm_profile", "") for row in plot_rows]
    baseline = rows_by_condition(rows)["E1"]
    metrics = [
        ("PRs per Engineer mean", "PRs"),
        ("avg_energy mean", "Energy"),
        ("Change Failure Rate (%) mean", "CFR"),
        ("domain_mismatch_count mean", "Mismatch"),
    ]
    x_positions = list(range(len(labels)))
    bar_width = 0.18
    start_offset = -bar_width * (len(metrics) - 1) / 2

    fig, ax = plt.subplots(figsize=(10, 5))
    for metric_index, (metric, label) in enumerate(metrics):
        offset = start_offset + metric_index * bar_width
        baseline_value = to_float(baseline.get(metric))
        values = [
            pct_change(row.get(metric), baseline_value) or 0.0
            for row in plot_rows
        ]
        xs = [position + offset for position in x_positions]
        ax.bar(xs, values, width=bar_width, label=label)

    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_title("Scenario E: PM Impact Summary")
    ax.set_xlabel("PM Profile")
    ax.set_ylabel("Percent Change vs weak_pm")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.grid(True, axis="y")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_bar_chart(labels, values, title, xlabel, ylabel, path):
    plt = get_pyplot()
    fig, ax = plt.subplots()
    ax.bar(labels, values)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y")
    ax.tick_params(axis="x", labelrotation=35)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_scatter_with_labels(rows, x_key, y_key, title, xlabel, ylabel, path):
    plt = get_pyplot()
    fig, ax = plt.subplots()
    xs = [to_float(row.get(x_key)) for row in rows]
    ys = [to_float(row.get(y_key)) for row in rows]
    ax.scatter(xs, ys)
    for row, x_value, y_value in zip(rows, xs, ys):
        ax.annotate(row.get("condition_id", ""), (x_value, y_value), textcoords="offset points", xytext=(4, 4))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_heatmap(all_rows: dict[str, list[dict]], path: Path):
    plt = get_pyplot()
    comparisons = [
        ("A2->A4", "A", "A2", "A4"),
        ("B1->B4", "B", "B1", "B4"),
        ("B5->B8", "B", "B5", "B8"),
        ("C1->C5", "C", "C1", "C5"),
        ("C6->C10", "C", "C6", "C10"),
    ]
    metrics = [
        "PRs per Engineer mean",
        "Lead Time (steps) mean",
        "Change Failure Rate (%) mean",
        "avg_energy mean",
        "remaining_backlog mean",
    ]
    matrix = []
    for _, scenario_id, baseline_id, target_id in comparisons:
        by_condition = rows_by_condition(all_rows[scenario_id])
        baseline = by_condition[baseline_id]
        target = by_condition[target_id]
        matrix.append([pct_change(target.get(metric), baseline.get(metric)) or 0.0 for metric in metrics])

    fig, ax = plt.subplots()
    image = ax.imshow(matrix, cmap="coolwarm")
    ax.set_title("Scenario Impact Heatmap")
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metrics, rotation=35, ha="right")
    ax.set_yticks(range(len(comparisons)))
    ax.set_yticklabels([comparison[0] for comparison in comparisons])
    for row_index, row_values in enumerate(matrix):
        for col_index, value in enumerate(row_values):
            ax.text(col_index, row_index, f"{value:.1f}", ha="center", va="center")
    fig.colorbar(image, ax=ax, label="Percent Change")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_figures(all_rows: dict[str, list[dict]], impact_rows: list[dict]) -> list[Path]:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    figure_paths = []

    def add_line(filename, rows, x_key, y_key, group_key, title, xlabel, ylabel):
        path = FIGURE_DIR / filename
        save_line_chart(rows, x_key, y_key, group_key, title, xlabel, ylabel, path)
        figure_paths.append(path)

    add_line("scenario_A_meeting_vs_prs.png", all_rows["A"], "meeting_load", "PRs per Engineer mean", "requirement_clarity", "Scenario A: Meeting Load vs PRs per Engineer", "Meeting Load", "PRs per Engineer")
    add_line("scenario_A_meeting_vs_energy.png", all_rows["A"], "meeting_load", "avg_energy mean", "requirement_clarity", "Scenario A: Meeting Load vs Energy", "Meeting Load", "Average Energy")
    add_line("scenario_A_clarity_vs_cfr.png", all_rows["A"], "meeting_load", "Change Failure Rate (%) mean", "requirement_clarity", "Scenario A: CFR by Meeting Load and Requirement Clarity", "Meeting Load", "Change Failure Rate (%)")
    add_line("scenario_A_meeting_vs_coaching.png", all_rows["A"], "meeting_load", "coaching_count mean", "requirement_clarity", "Scenario A: Meeting Load vs Coaching", "Meeting Load", "Coaching Count")
    add_line("scenario_B_review_vs_cfr.png", all_rows["B"], "review_strictness", "Change Failure Rate (%) mean", "codebase_stability", "Scenario B: Review Strictness vs CFR", "Review Strictness", "Change Failure Rate (%)")
    add_line("scenario_B_review_vs_lead_time.png", all_rows["B"], "review_strictness", "Lead Time (steps) mean", "codebase_stability", "Scenario B: Review Strictness vs Lead Time", "Review Strictness", "Lead Time (steps)")

    path = FIGURE_DIR / "scenario_B_quality_speed_tradeoff.png"
    save_scatter_with_labels(all_rows["B"], "Lead Time (steps) mean", "Change Failure Rate (%) mean", "Scenario B: Quality-Speed Trade-off", "Lead Time (steps)", "Change Failure Rate (%)", path)
    figure_paths.append(path)

    add_line("scenario_C_backlog_vs_prs.png", all_rows["C"], "sprint_backlog_size", "PRs per Engineer mean", "team_awareness", "Scenario C: Backlog vs PRs per Engineer", "Sprint Backlog Size", "PRs per Engineer")
    add_line("scenario_C_backlog_vs_energy.png", all_rows["C"], "sprint_backlog_size", "avg_energy mean", "team_awareness", "Scenario C: Backlog vs Energy", "Sprint Backlog Size", "Average Energy")
    add_line("scenario_C_backlog_vs_remaining_backlog.png", all_rows["C"], "sprint_backlog_size", "remaining_backlog mean", "team_awareness", "Scenario C: Backlog vs Remaining Backlog", "Sprint Backlog Size", "Remaining Backlog")
    add_line("scenario_C_backlog_vs_attrition.png", all_rows["C"], "sprint_backlog_size", "attrition_count mean", "team_awareness", "Scenario C: Backlog vs Attrition", "Sprint Backlog Size", "Attrition Count")

    if "D" in all_rows:
        scenario_d_figures = [
            (
                "scenario_D_team_composition_vs_prs.png",
                "PRs per Engineer mean",
                "Scenario D: Team Composition vs PRs per Engineer",
                "PRs per Engineer",
            ),
            (
                "scenario_D_mentoring_vs_resolution_rate.png",
                "help_request_resolution_rate mean",
                "Scenario D: Mentoring Intensity vs Help Resolution Rate",
                "Help Resolution Rate",
            ),
            (
                "scenario_D_mentoring_vs_knowledge_gain.png",
                "avg_knowledge_gain_from_help mean",
                "Scenario D: Mentoring Intensity vs Knowledge Gain",
                "Average Knowledge Gain from Help",
            ),
            (
                "scenario_D_mentoring_vs_helper_interruptions.png",
                "helper_interruptions mean",
                "Scenario D: Mentoring Intensity vs Helper Interruptions",
                "Helper Interruptions",
            ),
            (
                "scenario_D_mentoring_load_tradeoff.png",
                "mentoring_load_total mean",
                "Scenario D: Mentoring Load Trade-off",
                "Mentoring Load Total",
            ),
        ]
        for filename, y_key, title, ylabel in scenario_d_figures:
            path = FIGURE_DIR / filename
            save_team_composition_line_chart(
                all_rows["D"],
                y_key,
                title,
                ylabel,
                path,
            )
            figure_paths.append(path)

    if "E" in all_rows:
        scenario_e_rows = all_rows["E"]
        scenario_e_figures = [
            (
                "scenario_E_pm_profile_vs_prs.png",
                "PRs per Engineer mean",
                "Scenario E: PM Profile vs PRs per Engineer",
                "PRs per Engineer",
            ),
            (
                "scenario_E_pm_profile_vs_energy.png",
                "avg_energy mean",
                "Scenario E: PM Profile vs Avg Energy",
                "Avg Energy",
            ),
        ]
        for filename, y_key, title, ylabel in scenario_e_figures:
            path = FIGURE_DIR / filename
            save_pm_profile_bar_chart(scenario_e_rows, y_key, title, ylabel, path)
            figure_paths.append(path)

        grouped_e_figures = [
            (
                "scenario_E_allocation_match_vs_mismatch.png",
                [
                    ("allocation_match_score mean", "Allocation Match Score"),
                    ("domain_mismatch_count mean", "Domain Mismatch Count"),
                ],
                "Scenario E: Allocation Match and Domain Mismatch",
                "Value",
            ),
            (
                "scenario_E_requirement_coordination_vs_cfr.png",
                [
                    ("effective_requirement_clarity mean", "Effective Requirement Clarity"),
                    ("Change Failure Rate (%) mean", "Change Failure Rate (%)"),
                ],
                "Scenario E: Requirement Coordination and CFR",
                "Value",
            ),
            (
                "scenario_E_bottleneck_interventions.png",
                [
                    ("bottleneck_interventions mean", "Bottleneck Interventions"),
                    ("reassignments mean", "Reassignments"),
                ],
                "Scenario E: Bottleneck Interventions and Reassignments",
                "Count",
            ),
        ]
        for filename, series_specs, title, ylabel in grouped_e_figures:
            path = FIGURE_DIR / filename
            save_pm_profile_grouped_bar_chart(
                scenario_e_rows,
                series_specs,
                title,
                ylabel,
                path,
            )
            figure_paths.append(path)

        path = FIGURE_DIR / "scenario_E_pm_impact_summary.png"
        save_pm_impact_summary_chart(scenario_e_rows, path)
        figure_paths.append(path)

    sensitivity_labels = [
        "A2->A4 PRs",
        "A2->A4 energy",
        "B1->B4 CFR",
        "B5->B8 CFR",
        "C1->C5 energy",
        "C1->C5 backlog",
    ]
    impact_lookup = {
        (row["comparison"], row["key_metric"]): abs(to_float(row["change_pct"]) or 0.0)
        for row in impact_rows
    }
    sensitivity_values = [
        impact_lookup.get(("A2->A4", "PRs per Engineer mean"), 0.0),
        impact_lookup.get(("A2->A4", "avg_energy mean"), 0.0),
        impact_lookup.get(("B1->B4", "Change Failure Rate (%) mean"), 0.0),
        impact_lookup.get(("B5->B8", "Change Failure Rate (%) mean"), 0.0),
        impact_lookup.get(("C1->C5", "avg_energy mean"), 0.0),
        impact_lookup.get(("C1->C5", "remaining_backlog mean"), 0.0),
    ]
    path = FIGURE_DIR / "metric_sensitivity_summary.png"
    save_bar_chart(sensitivity_labels, sensitivity_values, "Metric Sensitivity Summary", "Scenario Comparison", "Absolute Percent Change", path)
    figure_paths.append(path)

    path = FIGURE_DIR / "scenario_impact_heatmap.png"
    save_heatmap(all_rows, path)
    figure_paths.append(path)
    return figure_paths


def read_available_summaries() -> dict[str, list[dict]]:
    all_rows = {}
    for scenario_id, path in SCENARIO_SUMMARIES.items():
        if scenario_id in {"D", "E"} and not path.exists():
            print(f"Scenario {scenario_id} summary not found, skipping {scenario_id} report assets: {path}")
            continue
        all_rows[scenario_id] = read_csv(path)
    return all_rows


def main() -> None:
    all_rows = read_available_summaries()
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    scenario_a_rows, scenario_a_fields = build_scenario_a_table(all_rows["A"])
    scenario_b_rows, scenario_b_fields = build_scenario_b_table(all_rows["B"])
    scenario_c_rows, scenario_c_fields = build_scenario_c_table(all_rows["C"])
    impact_rows, impact_fields = build_impact_summary(all_rows)

    tables = [
        (TABLE_DIR / "scenario_A_report_table.csv", scenario_a_rows, scenario_a_fields),
        (TABLE_DIR / "scenario_B_report_table.csv", scenario_b_rows, scenario_b_fields),
        (TABLE_DIR / "scenario_C_report_table.csv", scenario_c_rows, scenario_c_fields),
        (TABLE_DIR / "scenario_impact_summary.csv", impact_rows, impact_fields),
    ]
    if "D" in all_rows:
        scenario_d_rows, scenario_d_fields = build_scenario_d_table(all_rows["D"])
        scenario_d_impact_rows, scenario_d_impact_fields = build_scenario_d_impact_summary(all_rows["D"])
        tables.extend(
            [
                (TABLE_DIR / "scenario_D_report_table.csv", scenario_d_rows, scenario_d_fields),
                (TABLE_DIR / "scenario_D_impact_summary.csv", scenario_d_impact_rows, scenario_d_impact_fields),
            ]
        )
    if "E" in all_rows:
        scenario_e_rows, scenario_e_fields = build_scenario_e_table(all_rows["E"])
        scenario_e_impact_rows, scenario_e_impact_fields = build_scenario_e_impact_summary(all_rows["E"])
        tables.extend(
            [
                (TABLE_DIR / "scenario_E_report_table.csv", scenario_e_rows, scenario_e_fields),
                (TABLE_DIR / "scenario_E_impact_summary.csv", scenario_e_impact_rows, scenario_e_impact_fields),
            ]
        )

    for path, rows, fields in tables:
        write_csv(path, rows, fields)
        print(f"Wrote {len(rows)} rows to {path}")

    figure_paths = save_figures(all_rows, impact_rows)
    for path in figure_paths:
        print(f"Wrote figure: {path}")


if __name__ == "__main__":
    main()
