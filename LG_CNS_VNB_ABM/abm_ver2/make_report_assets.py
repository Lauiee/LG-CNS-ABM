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


def main() -> None:
    all_rows = {scenario_id: read_csv(path) for scenario_id, path in SCENARIO_SUMMARIES.items()}
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
    for path, rows, fields in tables:
        write_csv(path, rows, fields)
        print(f"Wrote {len(rows)} rows to {path}")

    figure_paths = save_figures(all_rows, impact_rows)
    for path in figure_paths:
        print(f"Wrote figure: {path}")


if __name__ == "__main__":
    main()
