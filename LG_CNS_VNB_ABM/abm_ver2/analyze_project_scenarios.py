#!/usr/bin/env python3
"""Summarize Scenario F/G recommendations by project type."""
import argparse
import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUTS_DIR = BASE_DIR / "outputs"
DEFAULT_REPORT_DIR = DEFAULT_OUTPUTS_DIR / "project_scenario_analysis"

SCENARIO_F = "F"
SCENARIO_G = "G"

SCENARIO_CONFIGS = {
    SCENARIO_F: {
        "comparison_column": "team_composition",
        "label": "team composition",
        "output_stem": "scenario_F_project_type_team_composition",
    },
    SCENARIO_G: {
        "comparison_column": "pm_profile",
        "label": "PM profile",
        "output_stem": "scenario_G_project_type_pm_profile",
    },
}

METRIC_COLUMNS = {
    "prs_per_engineer": "PRs per Engineer mean",
    "lead_time": "Lead Time (steps) mean",
    "change_failure_rate": "Change Failure Rate (%) mean",
    "avg_energy": "avg_energy mean",
    "rework_rate": "rework_rate mean",
    "senior_bottleneck_index": "senior_bottleneck_index mean",
    "remaining_backlog": "remaining_backlog mean",
}

METRIC_LABELS = {
    "prs_per_engineer": "PRs per Engineer",
    "lead_time": "Lead Time",
    "change_failure_rate": "Change Failure Rate",
    "avg_energy": "avg_energy",
    "rework_rate": "rework_rate",
    "senior_bottleneck_index": "senior_bottleneck_index",
    "remaining_backlog": "remaining_backlog",
}

BALANCED_SCORE_SPEC = [
    ("prs_per_engineer", "high"),
    ("lead_time", "low"),
    ("change_failure_rate", "low"),
    ("rework_rate", "low"),
    ("remaining_backlog", "low"),
    ("avg_energy", "high"),
]

QUALITY_SCORE_SPEC = [
    ("change_failure_rate", "low"),
    ("rework_rate", "low"),
]

THROUGHPUT_SCORE_SPEC = [
    ("prs_per_engineer", "high"),
    ("lead_time", "low"),
    ("remaining_backlog", "low"),
]

RECOMMENDATION_TYPES = [
    "throughput_best",
    "quality_best",
    "energy_best",
    "balanced_recommendation",
]


def summary_path_candidates(outputs_dir: Path, scenario_id: str) -> list[Path]:
    return [
        outputs_dir / f"scenario_{scenario_id}_final" / "experiment_summary.csv",
        outputs_dir / f"scenario_{scenario_id}" / "experiment_summary.csv",
        outputs_dir / "final" / f"scenario_{scenario_id}_summary.csv",
        outputs_dir / f"scenario_{scenario_id}_summary.csv",
        outputs_dir / "experiment_summary.csv",
    ]


def read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scenario_rows(path: Path, scenario_id: str) -> list[dict]:
    rows = read_csv_rows(path)
    return [
        row for row in rows
        if row.get("scenario_id", "").upper() == scenario_id
    ]


def find_summary_path(outputs_dir: Path, scenario_id: str, explicit_path: Path | None = None) -> Path | None:
    candidates = [explicit_path] if explicit_path else summary_path_candidates(outputs_dir, scenario_id)
    for path in candidates:
        if not path or not path.exists():
            continue
        if scenario_rows(path, scenario_id):
            return path
    return None


def to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_value(row: dict, metric_key: str) -> float | None:
    return to_float(row.get(METRIC_COLUMNS[metric_key]))


def normalized_values(rows: list[dict], metric_key: str, direction: str) -> dict[int, float | None]:
    values = {
        index: metric_value(row, metric_key)
        for index, row in enumerate(rows)
    }
    present = [value for value in values.values() if value is not None]
    if not present:
        return {index: None for index in values}

    minimum = min(present)
    maximum = max(present)
    if maximum == minimum:
        return {
            index: 0.5 if value is not None else None
            for index, value in values.items()
        }

    normalized = {}
    for index, value in values.items():
        if value is None:
            normalized[index] = None
            continue
        if direction == "high":
            normalized[index] = (value - minimum) / (maximum - minimum)
        else:
            normalized[index] = (maximum - value) / (maximum - minimum)
    return normalized


def score_rows(rows: list[dict], score_spec: list[tuple[str, str]]) -> list[float]:
    metric_scores = [
        normalized_values(rows, metric_key, direction)
        for metric_key, direction in score_spec
    ]
    scores = []
    for index, _row in enumerate(rows):
        components = [
            metric_score[index]
            for metric_score in metric_scores
            if metric_score[index] is not None
        ]
        scores.append(sum(components) / len(components) if components else 0.0)
    return scores


def best_index_by_score(rows: list[dict], scores: list[float], tie_breakers: list[tuple[str, str]]) -> int:
    tie_breaker_scores = [
        normalized_values(rows, metric_key, direction)
        for metric_key, direction in tie_breakers
    ]

    def sort_key(index: int):
        return (
            scores[index],
            *[
                metric_score[index] if metric_score[index] is not None else -1.0
                for metric_score in tie_breaker_scores
            ],
        )

    return max(range(len(rows)), key=sort_key)


def group_by_project_type(rows: list[dict], comparison_column: str) -> dict[str, list[dict]]:
    grouped = {}
    for row in rows:
        project_type = row.get("project_type", "")
        comparison_value = row.get(comparison_column, "")
        if not project_type or not comparison_value:
            continue
        grouped.setdefault(project_type, []).append(row)
    return grouped


def candidate_score_rows(
    scenario_id: str,
    rows: list[dict],
    comparison_column: str,
    source_path: Path,
) -> list[dict]:
    balanced_scores = score_rows(rows, BALANCED_SCORE_SPEC)
    throughput_scores = score_rows(rows, THROUGHPUT_SCORE_SPEC)
    quality_scores = score_rows(rows, QUALITY_SCORE_SPEC)
    energy_scores = score_rows(rows, [("avg_energy", "high")])

    output_rows = []
    for index, row in enumerate(rows):
        output_row = {
            "scenario_id": scenario_id,
            "project_type": row.get("project_type", ""),
            "comparison_dimension": comparison_column,
            "candidate": row.get(comparison_column, ""),
            "throughput_score": round(throughput_scores[index], 4),
            "quality_score": round(quality_scores[index], 4),
            "energy_score": round(energy_scores[index], 4),
            "balanced_score": round(balanced_scores[index], 4),
            "source_file": str(source_path),
        }
        for metric_key, column in METRIC_COLUMNS.items():
            output_row[column] = metric_value(row, metric_key)
        output_rows.append(output_row)
    return output_rows


def recommendation_record(
    scenario_id: str,
    recommendation_type: str,
    row: dict,
    comparison_column: str,
    score: float,
    source_path: Path,
) -> dict:
    record = {
        "scenario_id": scenario_id,
        "project_type": row.get("project_type", ""),
        "comparison_dimension": comparison_column,
        "recommendation_type": recommendation_type,
        "recommended_value": row.get(comparison_column, ""),
        "score": round(score, 4),
        "source_file": str(source_path),
    }
    for metric_key, column in METRIC_COLUMNS.items():
        record[column] = metric_value(row, metric_key)
    return record


def analyze_rows(
    scenario_id: str,
    rows: list[dict],
    comparison_column: str,
    source_path: Path,
) -> tuple[list[dict], list[dict]]:
    recommendations = []
    candidates = []

    for project_type, project_rows in sorted(group_by_project_type(rows, comparison_column).items()):
        candidates.extend(
            candidate_score_rows(scenario_id, project_rows, comparison_column, source_path)
        )

        throughput_scores = score_rows(project_rows, THROUGHPUT_SCORE_SPEC)
        quality_scores = score_rows(project_rows, QUALITY_SCORE_SPEC)
        energy_scores = score_rows(project_rows, [("avg_energy", "high")])
        balanced_scores = score_rows(project_rows, BALANCED_SCORE_SPEC)

        picks = {
            "throughput_best": (
                throughput_scores,
                [("prs_per_engineer", "high"), ("lead_time", "low"), ("remaining_backlog", "low")],
            ),
            "quality_best": (
                quality_scores,
                [("change_failure_rate", "low"), ("rework_rate", "low"), ("senior_bottleneck_index", "low")],
            ),
            "energy_best": (
                energy_scores,
                [("avg_energy", "high"), ("senior_bottleneck_index", "low")],
            ),
            "balanced_recommendation": (
                balanced_scores,
                BALANCED_SCORE_SPEC,
            ),
        }

        for recommendation_type in RECOMMENDATION_TYPES:
            scores, tie_breakers = picks[recommendation_type]
            best_index = best_index_by_score(project_rows, scores, tie_breakers)
            recommendations.append(
                recommendation_record(
                    scenario_id,
                    recommendation_type,
                    project_rows[best_index],
                    comparison_column,
                    scores[best_index],
                    source_path,
                )
            )

    return recommendations, candidates


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(headers: list[str], rows: list[list]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(format_markdown_value(value) for value in row) + " |")
    return "\n".join(lines)


def format_markdown_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def build_markdown(
    scenario_id: str,
    config: dict,
    recommendations: list[dict],
    candidates: list[dict],
    source_path: Path,
) -> str:
    comparison_label = config["label"]
    lines = [
        f"# Scenario {scenario_id} Project Type Recommendations",
        "",
        f"- Source: `{source_path}`",
        f"- Comparison: project_type x {comparison_label}",
        "- Balanced score: normalized average of high PRs per Engineer, low Lead Time, low Change Failure Rate, low rework_rate, low remaining_backlog, and high avg_energy.",
        "",
    ]

    project_types = sorted({row["project_type"] for row in recommendations})
    for project_type in project_types:
        lines.append(f"## {project_type}")
        lines.append("")
        rec_rows = [
            row for row in recommendations
            if row["project_type"] == project_type
        ]
        lines.append(markdown_table(
            [
                "Recommendation",
                "Selected",
                "Score",
                "PRs/Eng",
                "Lead Time",
                "CFR",
                "avg_energy",
                "rework_rate",
                "senior_bottleneck",
                "remaining_backlog",
            ],
            [
                [
                    row["recommendation_type"],
                    row["recommended_value"],
                    row["score"],
                    row[METRIC_COLUMNS["prs_per_engineer"]],
                    row[METRIC_COLUMNS["lead_time"]],
                    row[METRIC_COLUMNS["change_failure_rate"]],
                    row[METRIC_COLUMNS["avg_energy"]],
                    row[METRIC_COLUMNS["rework_rate"]],
                    row[METRIC_COLUMNS["senior_bottleneck_index"]],
                    row[METRIC_COLUMNS["remaining_backlog"]],
                ]
                for row in rec_rows
            ],
        ))
        lines.append("")

        candidate_rows = [
            row for row in candidates
            if row["project_type"] == project_type
        ]
        lines.append(markdown_table(
            [
                "Candidate",
                "Throughput",
                "Quality",
                "Energy",
                "Balanced",
            ],
            [
                [
                    row["candidate"],
                    row["throughput_score"],
                    row["quality_score"],
                    row["energy_score"],
                    row["balanced_score"],
                ]
                for row in candidate_rows
            ],
        ))
        lines.append("")

    return "\n".join(lines)


def analyze_scenario(
    scenario_id: str,
    outputs_dir: Path,
    report_dir: Path,
    explicit_path: Path | None = None,
    required: bool = False,
) -> tuple[Path | None, Path | None]:
    config = SCENARIO_CONFIGS[scenario_id]
    source_path = find_summary_path(outputs_dir, scenario_id, explicit_path)
    if source_path is None:
        if required:
            raise FileNotFoundError(
                f"Could not find Scenario {scenario_id} experiment_summary.csv under {outputs_dir}"
            )
        print(f"Scenario {scenario_id} summary not found; skipping.")
        return None, None

    rows = scenario_rows(source_path, scenario_id)
    recommendations, candidates = analyze_rows(
        scenario_id,
        rows,
        config["comparison_column"],
        source_path,
    )
    if not recommendations:
        if required:
            raise ValueError(
                f"Scenario {scenario_id} summary has no usable project_type x "
                f"{config['comparison_column']} rows: {source_path}"
            )
        print(f"Scenario {scenario_id} has no usable rows; skipping.")
        return None, None

    report_dir.mkdir(parents=True, exist_ok=True)
    stem = config["output_stem"]
    recommendation_csv = report_dir / f"{stem}_recommendations.csv"
    candidate_csv = report_dir / f"{stem}_candidate_scores.csv"
    markdown_path = report_dir / f"{stem}_recommendations.md"

    write_csv(recommendation_csv, recommendations)
    write_csv(candidate_csv, candidates)
    markdown_path.write_text(
        build_markdown(scenario_id, config, recommendations, candidates, source_path),
        encoding="utf-8",
    )

    print(f"Wrote Scenario {scenario_id} recommendations: {recommendation_csv}")
    print(f"Wrote Scenario {scenario_id} candidate scores: {candidate_csv}")
    print(f"Wrote Scenario {scenario_id} markdown: {markdown_path}")
    return recommendation_csv, markdown_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze Scenario F/G project-type recommendations."
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=DEFAULT_OUTPUTS_DIR,
        help="Directory containing scenario outputs.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Directory where CSV/Markdown summaries will be written.",
    )
    parser.add_argument(
        "--scenario-f-summary",
        type=Path,
        help="Explicit Scenario F summary CSV path.",
    )
    parser.add_argument(
        "--scenario-g-summary",
        type=Path,
        help="Explicit Scenario G summary CSV path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analyze_scenario(
        SCENARIO_F,
        args.outputs_dir,
        args.report_dir,
        explicit_path=args.scenario_f_summary,
        required=True,
    )
    analyze_scenario(
        SCENARIO_G,
        args.outputs_dir,
        args.report_dir,
        explicit_path=args.scenario_g_summary,
        required=False,
    )


if __name__ == "__main__":
    main()
