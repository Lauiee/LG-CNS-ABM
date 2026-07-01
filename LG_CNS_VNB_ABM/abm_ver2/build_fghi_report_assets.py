#!/usr/bin/env python3
"""Create visualization assets and structured notes for F/G/H/I ABM report."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch


BASE_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = BASE_DIR / "outputs" / "validation_runs" / "20260626_165229_calibrated"
REPORT_ROOT = BASE_DIR / "outputs" / "reports" / f"fghi_calibrated_report_{datetime.now():%Y%m%d_%H%M%S}"
FIG_DIR = REPORT_ROOT / "figures"
NOTE_PATH = REPORT_ROOT / "report_summary.json"

PROJECT_ORDER = [
    "new_build",
    "maintenance_enhancement",
    "legacy_migration",
    "deadline_driven",
    "quality_critical",
]
PROJECT_LABELS = {
    "new_build": "신규 구축",
    "maintenance_enhancement": "유지보수/개선",
    "legacy_migration": "레거시 전환",
    "deadline_driven": "납기 중심",
    "quality_critical": "품질 중시",
}
TEAM_ORDER = ["junior_heavy", "balanced", "senior_heavy"]
TEAM_LABELS = {
    "junior_heavy": "주니어 중심",
    "balanced": "균형형",
    "senior_heavy": "시니어 중심",
}
PM_ORDER = [
    "weak_pm",
    "allocation_focused_pm",
    "bottleneck_focused_pm",
    "requirement_focused_pm",
    "strong_pm",
]
PM_LABELS = {
    "weak_pm": "약한 PM",
    "allocation_focused_pm": "배분 중심",
    "bottleneck_focused_pm": "병목 중심",
    "requirement_focused_pm": "요구사항 중심",
    "strong_pm": "강한 PM",
}
PM_I_ORDER = ["weak_pm", "requirement_focused_pm", "strong_pm"]
VOL_ORDER = [0.2, 0.5, 0.8]
H_PROJECT_ORDER = ["new_build", "legacy_migration", "deadline_driven"]
I_PROJECT_ORDER = ["new_build", "deadline_driven", "quality_critical"]

METRICS = {
    "prs": "PRs per Engineer mean",
    "lead": "Lead Time (steps) mean",
    "cfr": "Change Failure Rate (%) mean",
    "energy": "avg_energy mean",
    "rework": "rework_rate mean",
    "backlog": "remaining_backlog mean",
    "prs_cost": "PRs_per_cost mean",
    "tasks_cost": "completed_tasks_per_cost mean",
    "help": "help_resolution_rate mean",
    "senior_bottleneck": "senior_bottleneck_index mean",
    "senior_mentor": "senior_mentoring_load_per_senior mean",
    "senior_review": "senior_review_load_per_senior mean",
    "junior_knowledge": "junior_avg_knowledge mean",
    "scope": "scope_changes mean",
    "scope_prevented": "scope_changes_prevented mean",
    "clarification": "clarification_events mean",
    "pm_capacity": "pm_capacity_used mean",
}

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}
COLORS = {
    "blue": {"xlight": "#EAF1FE", "light": "#CEDFFE", "base": "#A3BEFA", "mid": "#5477C4", "dark": "#2E4780"},
    "gold": {"xlight": "#FFF4C2", "light": "#FFEA8F", "base": "#FFE15B", "mid": "#B8A037", "dark": "#736422"},
    "orange": {"xlight": "#FFEDDE", "light": "#FFBDA1", "base": "#F0986E", "mid": "#CC6F47", "dark": "#804126"},
    "olive": {"xlight": "#D8ECBD", "light": "#BEEB96", "base": "#A3D576", "mid": "#71B436", "dark": "#386411"},
    "pink": {"xlight": "#FCDAD6", "light": "#F5BACC", "base": "#F390CA", "mid": "#BD569B", "dark": "#8A3A6F"},
}
LINE_COLORS = [COLORS["blue"]["mid"], COLORS["orange"]["mid"], COLORS["olive"]["mid"], COLORS["pink"]["mid"], COLORS["gold"]["mid"]]


def setup_matplotlib() -> None:
    font_candidates = [
        Path.home() / "Library" / "Fonts" / "NotoSansCJKkr-Regular.otf",
        Path.home() / "Library" / "Fonts" / "NanumSquareR.ttf",
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            fm.fontManager.addfont(str(font_path))
            font_name = fm.FontProperties(fname=str(font_path)).get_name()
            mpl.rcParams["font.family"] = font_name
            break
    mpl.rcParams.update({
        "figure.facecolor": TOKENS["surface"],
        "axes.facecolor": TOKENS["panel"],
        "axes.edgecolor": TOKENS["axis"],
        "axes.labelcolor": TOKENS["ink"],
        "axes.titlecolor": TOKENS["ink"],
        "xtick.color": TOKENS["muted"],
        "ytick.color": TOKENS["muted"],
        "grid.color": TOKENS["grid"],
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.unicode_minus": False,
        "savefig.facecolor": TOKENS["surface"],
        "savefig.edgecolor": "none",
    })


def load_summary(scenario_id: str) -> pd.DataFrame:
    path = SOURCE_ROOT / f"scenario_{scenario_id}" / "experiment_summary.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def round_float(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def label_project(value: str) -> str:
    return PROJECT_LABELS.get(value, value)


def label_team(value: str) -> str:
    return TEAM_LABELS.get(value, value)


def label_pm(value: str) -> str:
    return PM_LABELS.get(value, value)


def heat_cmap(root: str) -> LinearSegmentedColormap:
    family = COLORS[root]
    return LinearSegmentedColormap.from_list(
        f"{root}_report",
        [TOKENS["panel"], family["xlight"], family["light"], family["base"], family["mid"]],
    )


def heatmap(
    ax,
    df: pd.DataFrame,
    row_col: str,
    col_col: str,
    value_col: str,
    row_order: list,
    col_order: list,
    row_labeler,
    col_labeler,
    title: str,
    fmt: str = ".2f",
    cmap_root: str = "blue",
) -> None:
    pivot = (
        df.pivot(index=row_col, columns=col_col, values=value_col)
        .reindex(index=row_order, columns=col_order)
    )
    values = pivot.to_numpy(dtype=float)
    valid = values[np.isfinite(values)]
    if valid.size:
        vmin, vmax = float(valid.min()), float(valid.max())
        if vmin == vmax:
            vmin, vmax = vmin - 0.5, vmax + 0.5
    else:
        vmin, vmax = 0.0, 1.0
    im = ax.imshow(values, aspect="auto", cmap=heat_cmap(cmap_root), vmin=vmin, vmax=vmax)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", pad=8)
    ax.set_xticks(np.arange(len(col_order)), [col_labeler(v) for v in col_order], fontsize=9)
    ax.set_yticks(np.arange(len(row_order)), [row_labeler(v) for v in row_order], fontsize=9)
    ax.tick_params(length=0)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            if np.isfinite(values[i, j]):
                ax.text(j, i, format(values[i, j], fmt), ha="center", va="center", fontsize=8.5, color=TOKENS["ink"])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return im


def save_figure(fig, name: str) -> dict:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    png = FIG_DIR / f"{name}.png"
    svg = FIG_DIR / f"{name}.svg"
    fig.savefig(png, dpi=220, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)
    return {"png": str(png), "svg": str(svg)}


def add_footer(fig, source_text: str) -> None:
    fig.text(0.01, 0.012, source_text, fontsize=8.5, color=TOKENS["muted"], ha="left")


def line_grid(
    df: pd.DataFrame,
    project_order: list,
    x_col: str,
    series_col: str,
    series_order: list,
    metrics: list[tuple[str, str, str]],
    series_labeler,
    title: str,
    subtitle: str,
    name: str,
) -> dict:
    nrows = len(metrics)
    ncols = len(project_order)
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, max(7.8, 3.4 * nrows)), squeeze=False)
    fig.suptitle(title, fontsize=17, fontweight="bold", color=TOKENS["ink"], x=0.02, ha="left", y=0.965)
    fig.text(0.02, 0.925, subtitle, fontsize=10.5, color=TOKENS["muted"], ha="left")
    for row_idx, (metric_col, metric_label, y_fmt) in enumerate(metrics):
        for col_idx, project in enumerate(project_order):
            ax = axes[row_idx][col_idx]
            part = df[df["project_type"] == project]
            for idx, series in enumerate(series_order):
                line = part[part[series_col] == series].sort_values(x_col)
                if line.empty:
                    continue
                ax.plot(
                    line[x_col],
                    line[metric_col],
                    marker="o",
                    linewidth=1.8,
                    markersize=4.2,
                    color=LINE_COLORS[idx % len(LINE_COLORS)],
                    label=series_labeler(series),
                )
            if row_idx == 0:
                ax.set_title(label_project(project), fontsize=11, fontweight="bold", color=TOKENS["ink"])
            if col_idx == 0:
                ax.set_ylabel(metric_label, fontsize=9.5, color=TOKENS["ink"])
            ax.grid(True, axis="y")
            ax.set_xlabel("")
            ax.tick_params(axis="both", labelsize=8.5)
            if y_fmt == "pct":
                ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
            if x_col == "mentoring_intensity":
                ax.set_xticks([0.2, 0.5, 0.8])
            elif x_col == "requirement_volatility":
                ax.set_xticks([0.2, 0.5, 0.8])
            if row_idx == 0 and col_idx == ncols - 1:
                ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False, fontsize=8.5)
    add_footer(fig, "데이터: calibrated validation summary CSV, 각 조건 100회 반복 평균")
    fig.tight_layout(rect=[0, 0.03, 0.94, 0.86])
    return save_figure(fig, name)


def plot_scenario_f(df: pd.DataFrame) -> dict:
    panels = [
        (METRICS["prs"], "PRs per Engineer", ".2f", "blue"),
        (METRICS["prs_cost"], "PRs per Cost", ".2f", "blue"),
        (METRICS["lead"], "Lead Time", ".2f", "orange"),
        (METRICS["rework"], "Rework Rate", ".2f", "orange"),
        (METRICS["backlog"], "Remaining Backlog", ".0f", "orange"),
        (METRICS["senior_mentor"], "Senior Mentoring Load / Senior", ".1f", "orange"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(16, 9.5))
    fig.suptitle("Scenario F: 프로젝트 유형 × 팀 구성", fontsize=17, fontweight="bold", x=0.02, ha="left", y=0.995)
    fig.text(0.02, 0.96, "팀 구성별 처리량, 비용 효율, 품질 부담, 시니어 부하를 비교", fontsize=10.5, color=TOKENS["muted"], ha="left")
    for ax, (metric, title, fmt, cmap_root) in zip(axes.flat, panels):
        heatmap(ax, df, "project_type", "team_composition", metric, PROJECT_ORDER, TEAM_ORDER, label_project, label_team, title, fmt, cmap_root)
    add_footer(fig, "데이터: Scenario F summary CSV, 각 조건 100회 반복 평균")
    fig.tight_layout(rect=[0, 0.03, 1, 0.92])
    return save_figure(fig, "scenario_F_team_composition_dashboard")


def plot_scenario_g(df: pd.DataFrame) -> dict:
    panels = [
        (METRICS["cfr"], "Change Failure Rate (%)", ".1f", "orange"),
        (METRICS["rework"], "Rework Rate", ".2f", "orange"),
        (METRICS["scope_prevented"], "Scope Changes Prevented", ".1f", "blue"),
        (METRICS["scope"], "Scope Changes", ".1f", "orange"),
        (METRICS["energy"], "Average Energy", ".1f", "blue"),
        (METRICS["pm_capacity"], "PM Capacity Used", ".1f", "gold"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(18, 9.5))
    fig.suptitle("Scenario G: 프로젝트 유형 × PM Profile", fontsize=17, fontweight="bold", x=0.02, ha="left", y=0.995)
    fig.text(0.02, 0.96, "PM 역량 조합에 따른 품질, 범위관리, 팀 에너지 변화를 비교", fontsize=10.5, color=TOKENS["muted"], ha="left")
    for ax, (metric, title, fmt, cmap_root) in zip(axes.flat, panels):
        heatmap(ax, df, "project_type", "pm_profile", metric, PROJECT_ORDER, PM_ORDER, label_project, label_pm, title, fmt, cmap_root)
        ax.tick_params(axis="x", labelrotation=20)
    add_footer(fig, "데이터: Scenario G summary CSV, 각 조건 100회 반복 평균")
    fig.tight_layout(rect=[0, 0.03, 1, 0.92])
    return save_figure(fig, "scenario_G_pm_profile_dashboard")


def plot_scenario_h(df: pd.DataFrame) -> dict:
    first = line_grid(
        df=df,
        project_order=H_PROJECT_ORDER,
        x_col="mentoring_intensity",
        series_col="team_composition",
        series_order=TEAM_ORDER,
        metrics=[
            (METRICS["help"], "Help Resolution Rate", "pct"),
            (METRICS["senior_mentor"], "Senior Mentoring Load / Senior", "num"),
        ],
        series_labeler=label_team,
        title="Scenario H-1: 멘토링 강도에 따른 도움 해결률과 시니어 부하",
        subtitle="멘토링 강도가 높아질수록 도움 해결률과 시니어 멘토링 부하가 함께 변화하는지 확인",
        name="scenario_H_mentoring_help_load_dashboard",
    )
    second = line_grid(
        df=df,
        project_order=H_PROJECT_ORDER,
        x_col="mentoring_intensity",
        series_col="team_composition",
        series_order=TEAM_ORDER,
        metrics=[
            (METRICS["senior_bottleneck"], "Senior Bottleneck Index", "num"),
            (METRICS["rework"], "Rework Rate", "num"),
            (METRICS["energy"], "Average Energy", "num"),
        ],
        series_labeler=label_team,
        title="Scenario H-2: 멘토링 강도에 따른 병목, 재작업, 에너지",
        subtitle="팀 구성별로 멘토링 강도 조정이 운영 부담과 품질 지표에 미치는 방향을 비교",
        name="scenario_H_mentoring_quality_energy_dashboard",
    )
    return {"help_load": first, "quality_energy": second}


def plot_scenario_i(df: pd.DataFrame) -> dict:
    first = line_grid(
        df=df,
        project_order=I_PROJECT_ORDER,
        x_col="requirement_volatility",
        series_col="pm_profile",
        series_order=PM_I_ORDER,
        metrics=[
            (METRICS["rework"], "Rework Rate", "num"),
            (METRICS["scope"], "Scope Changes", "num"),
            (METRICS["scope_prevented"], "Scope Changes Prevented", "num"),
        ],
        series_labeler=label_pm,
        title="Scenario I-1: 요구사항 변동성과 범위관리",
        subtitle="요구사항 변동성이 커질 때 PM profile별 재작업과 scope change 대응 수준을 비교",
        name="scenario_I_volatility_rework_scope_dashboard",
    )
    second = line_grid(
        df=df,
        project_order=I_PROJECT_ORDER,
        x_col="requirement_volatility",
        series_col="pm_profile",
        series_order=PM_I_ORDER,
        metrics=[
            (METRICS["lead"], "Lead Time", "num"),
            (METRICS["cfr"], "Change Failure Rate (%)", "num"),
            (METRICS["energy"], "Average Energy", "num"),
        ],
        series_labeler=label_pm,
        title="Scenario I-2: 요구사항 변동성과 납기/품질/에너지",
        subtitle="변동성 증가가 리드타임, 장애율, 평균 에너지에 어떻게 반영되는지 비교",
        name="scenario_I_volatility_quality_energy_dashboard",
    )
    return {"rework_scope": first, "quality_energy": second}


def scenario_notes(data: dict[str, pd.DataFrame], figures: dict) -> dict:
    f = data["F"]
    g = data["G"]
    h = data["H"]
    i = data["I"]

    f_team = f.groupby("team_composition")[
        [METRICS["prs"], METRICS["prs_cost"], METRICS["tasks_cost"], METRICS["backlog"], METRICS["senior_mentor"]]
    ].mean()
    f_best_prs_team = f_team[METRICS["prs"]].idxmax()
    f_best_tasks_cost_team = f_team[METRICS["tasks_cost"]].idxmax()
    f_lowest_backlog_team = f_team[METRICS["backlog"]].idxmin()

    g_pm = g.groupby("pm_profile")[
        [METRICS["cfr"], METRICS["rework"], METRICS["scope"], METRICS["scope_prevented"], METRICS["energy"], METRICS["pm_capacity"]]
    ].mean()
    g_low_rework_pm = g_pm[METRICS["rework"]].idxmin()
    g_low_cfr_pm = g_pm[METRICS["cfr"]].idxmin()
    g_high_scope_pm = g_pm[METRICS["scope_prevented"]].idxmax()

    h_intensity = h.groupby("mentoring_intensity")[
        [METRICS["help"], METRICS["senior_mentor"], METRICS["senior_bottleneck"], METRICS["rework"], METRICS["energy"]]
    ].mean()
    h_low = h_intensity.loc[0.2]
    h_high = h_intensity.loc[0.8]
    h_team = h.groupby("team_composition")[
        [METRICS["help"], METRICS["senior_mentor"], METRICS["senior_bottleneck"], METRICS["rework"], METRICS["energy"]]
    ].mean()
    h_high_load_team = h_team[METRICS["senior_mentor"]].idxmax()

    i_vol = i.groupby("requirement_volatility")[
        [METRICS["rework"], METRICS["scope"], METRICS["scope_prevented"], METRICS["lead"], METRICS["cfr"], METRICS["energy"]]
    ].mean()
    i_pm = i.groupby("pm_profile")[
        [METRICS["rework"], METRICS["scope"], METRICS["scope_prevented"], METRICS["cfr"], METRICS["energy"], METRICS["pm_capacity"]]
    ].mean()
    i_low_rework_pm = i_pm[METRICS["rework"]].idxmin()
    i_high_scope_pm = i_pm[METRICS["scope_prevented"]].idxmax()
    i_low_cfr_pm = i_pm[METRICS["cfr"]].idxmin()

    return {
        "meta": {
            "source_root": str(SOURCE_ROOT),
            "report_root": str(REPORT_ROOT),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "runs": 100,
            "sprints": 6,
        },
        "figures": figures,
        "summary": [
            f"F: 시니어 중심 팀은 평균 PRs per Engineer가 {round_float(f_team.loc[f_best_prs_team, METRICS['prs']])}로 가장 높고, 잔여 백로그도 {round_float(f_team.loc[f_lowest_backlog_team, METRICS['backlog']], 1)}로 가장 낮았다.",
            f"F: 주니어 중심 팀은 completed tasks per cost가 {round_float(f_team.loc[f_best_tasks_cost_team, METRICS['tasks_cost']])}로 가장 높아, 비용 대비 완료량 관점에서는 다른 해석이 가능하다.",
            f"G: strong PM은 평균 scope changes prevented가 {round_float(g_pm.loc[g_high_scope_pm, METRICS['scope_prevented']])}로 가장 높고, rework rate가 {round_float(g_pm.loc[g_low_rework_pm, METRICS['rework']])}로 가장 낮았다.",
            f"H: 멘토링 강도 0.2에서 0.8로 높아질 때 help resolution rate 평균은 {round_float(h_low[METRICS['help']])}에서 {round_float(h_high[METRICS['help']])}로 상승했다.",
            f"H: 같은 구간에서 senior mentoring load per senior는 {round_float(h_low[METRICS['senior_mentor']])}에서 {round_float(h_high[METRICS['senior_mentor']])}로 상승했다.",
            f"I: requirement volatility 0.2에서 0.8로 높아질 때 rework rate 평균은 {round_float(i_vol.loc[0.2, METRICS['rework']])}에서 {round_float(i_vol.loc[0.8, METRICS['rework']])}로 증가했다.",
            f"I: strong PM은 scope changes prevented 평균 {round_float(i_pm.loc[i_high_scope_pm, METRICS['scope_prevented']])}, rework rate 평균 {round_float(i_pm.loc[i_low_rework_pm, METRICS['rework']])}로 변동성 대응력이 가장 강하게 나타났다.",
        ],
        "scenarios": {
            "F": {
                "title": "Scenario F: 프로젝트 유형 × 팀 구성",
                "purpose": [
                    "프로젝트 유형별로 적합한 팀 구성 차이를 확인한다.",
                    "주니어 중심, 균형형, 시니어 중심 구성이 처리량, 비용 효율, 재작업, 잔여 백로그에 미치는 차이를 비교한다.",
                    "프로젝트 특성에 따라 동일한 팀 구성이 다른 성과를 낼 수 있는지 확인한다.",
                ],
                "meaning": [
                    "LG CNS 프로젝트형 개발조직에서는 인력 구성 자체가 비용과 납기, 품질을 동시에 바꾸는 핵심 변수다.",
                    "기존 PRISM 지표 외에 staffing cost 기반 지표를 함께 보아야 팀 구성의 경제성을 판단할 수 있다.",
                    "시니어 비중 확대가 항상 비용 효율까지 우월한지 별도로 확인할 수 있다.",
                ],
                "results": [
                    f"시니어 중심 팀은 평균 PRs per Engineer {round_float(f_team.loc['senior_heavy', METRICS['prs']])}로 가장 높았다.",
                    f"시니어 중심 팀은 평균 PRs per Cost {round_float(f_team.loc['senior_heavy', METRICS['prs_cost']])}로도 가장 높았다.",
                    f"주니어 중심 팀은 completed tasks per cost {round_float(f_team.loc['junior_heavy', METRICS['tasks_cost']])}로 가장 높았다.",
                    f"시니어 중심 팀은 평균 remaining backlog {round_float(f_team.loc['senior_heavy', METRICS['backlog']], 1)}로 가장 낮았다.",
                    f"주니어 중심 팀은 senior mentoring load per senior {round_float(f_team.loc['junior_heavy', METRICS['senior_mentor']], 1)}로 가장 높았다.",
                ],
                "interpretation": [
                    "처리량과 잔여 백로그 기준으로는 시니어 중심 구성이 가장 안정적으로 나타났다.",
                    "완료 업무 수를 비용으로 나누면 주니어 중심 구성이 높게 나타나, 비용 기준 평가는 PR 기준 평가와 다르다.",
                    "주니어 중심 구성은 시니어 1인당 멘토링 부담이 크게 증가해 운영 병목 위험을 키운다.",
                    "레거시 전환과 납기 중심 프로젝트에서는 재작업률과 잔여 백로그가 상대적으로 커, 단순 처리량만으로 적합성을 판단하기 어렵다.",
                ],
            },
            "G": {
                "title": "Scenario G: 프로젝트 유형 × PM Profile",
                "purpose": [
                    "PM profile별 조정 역량이 프로젝트 유형별 성과에 미치는 영향을 확인한다.",
                    "배분, 병목 탐지, 요구사항 조율, scope control의 조합이 품질과 에너지에 미치는 차이를 비교한다.",
                    "PM 개입이 scope change와 재작업을 줄이는지 확인한다.",
                ],
                "meaning": [
                    "프로젝트형 조직에서는 PM 역량이 개발자 생산성뿐 아니라 요구사항 안정성과 장애율에 영향을 줄 수 있다.",
                    "PM profile을 분리하면 어떤 PM 역량이 어떤 지표에 더 민감한지 확인할 수 있다.",
                    "강한 PM profile은 효과와 함께 PM capacity 사용량도 증가하므로 운영 비용 관점의 해석이 필요하다.",
                ],
                "results": [
                    f"strong PM은 scope changes prevented 평균 {round_float(g_pm.loc['strong_pm', METRICS['scope_prevented']])}로 가장 높았다.",
                    f"strong PM은 scope changes 평균 {round_float(g_pm.loc['strong_pm', METRICS['scope']])}로 가장 낮았다.",
                    f"strong PM은 rework rate 평균 {round_float(g_pm.loc['strong_pm', METRICS['rework']])}로 가장 낮았다.",
                    f"requirement focused PM은 Change Failure Rate 평균 {round_float(g_pm.loc['requirement_focused_pm', METRICS['cfr']])}%로 가장 낮았다.",
                    f"strong PM은 PM capacity used 평균 {round_float(g_pm.loc['strong_pm', METRICS['pm_capacity']])}로 가장 높았다.",
                ],
                "interpretation": [
                    "scope control과 요구사항 조율이 강한 PM은 범위 변경과 재작업을 줄이는 방향으로 작동했다.",
                    "품질 지표만 보면 requirement focused PM이 강하게 나타나며, 요구사항 명확화가 장애율을 낮추는 경로로 해석된다.",
                    "strong PM은 효과가 크지만 PM capacity 소모도 가장 커, 모델상 개입 비용이 함께 증가한다.",
                    "quality critical 프로젝트에서는 PM profile 간 CFR 차이가 작아, 프로젝트 archetype 자체의 품질 gate 영향이 크게 작동한 것으로 해석된다.",
                ],
            },
            "H": {
                "title": "Scenario H: 팀 구성 × 멘토링 강도 × 프로젝트 유형",
                "purpose": [
                    "멘토링 강도 변화가 도움 해결률, 시니어 부하, 병목, 재작업에 미치는 영향을 확인한다.",
                    "주니어 중심, 균형형, 시니어 중심 팀에서 멘토링 강도의 효과가 다르게 나타나는지 비교한다.",
                    "프로젝트 유형별로 멘토링 강화가 품질과 에너지에 어떤 방향으로 작동하는지 확인한다.",
                ],
                "meaning": [
                    "멘토링은 지식 이전과 문제 해결을 돕지만, 동시에 시니어의 운영 부하를 증가시킨다.",
                    "팀 구성과 프로젝트 유형에 따라 동일한 멘토링 정책의 효과가 달라질 수 있다.",
                    "도움 해결률 개선과 시니어 병목 위험을 함께 봐야 멘토링 강도의 적정성을 판단할 수 있다.",
                ],
                "results": [
                    f"멘토링 강도 0.2에서 help resolution rate 평균은 {round_float(h_low[METRICS['help']])}였다.",
                    f"멘토링 강도 0.8에서 help resolution rate 평균은 {round_float(h_high[METRICS['help']])}였다.",
                    f"멘토링 강도 0.2에서 senior mentoring load per senior 평균은 {round_float(h_low[METRICS['senior_mentor']])}였다.",
                    f"멘토링 강도 0.8에서 senior mentoring load per senior 평균은 {round_float(h_high[METRICS['senior_mentor']])}였다.",
                    f"주니어 중심 팀은 senior mentoring load per senior 평균 {round_float(h_team.loc['junior_heavy', METRICS['senior_mentor']])}로 가장 높았다.",
                ],
                "interpretation": [
                    "멘토링 강도를 높이면 도움 해결률은 뚜렷하게 개선된다.",
                    "동시에 시니어 1인당 멘토링 부하가 크게 증가해, 특히 주니어 중심 팀에서 병목 비용이 커진다.",
                    "senior bottleneck index는 평균적으로 낮아지는 방향이지만, 멘토링 부하 자체는 증가한다.",
                    "재작업률은 멘토링 강도만으로 뚜렷하게 감소하지 않아, 요구사항 변동성과 도메인 적합성도 함께 관리되어야 한다.",
                ],
            },
            "I": {
                "title": "Scenario I: 요구사항 변동성 × PM Requirement Coordination",
                "purpose": [
                    "요구사항 변동성이 rework, scope change, lead time, CFR에 미치는 영향을 확인한다.",
                    "weak PM, requirement focused PM, strong PM이 변동성 증가 상황에서 다르게 대응하는지 비교한다.",
                    "project type 기본값보다 scenario 조건의 requirement volatility가 우선되는 실험 효과를 확인한다.",
                ],
                "meaning": [
                    "요구사항 변동성은 프로젝트형 개발조직의 재작업과 일정 압박을 직접적으로 키우는 요인이다.",
                    "PM의 요구사항 조율과 scope control은 변동성의 영향을 완충하는 운영 장치로 볼 수 있다.",
                    "품질 중시, 신규 구축, 납기 중심 프로젝트에서 변동성의 민감도가 어떻게 다른지 비교할 수 있다.",
                ],
                "results": [
                    f"requirement volatility 0.2에서 rework rate 평균은 {round_float(i_vol.loc[0.2, METRICS['rework']])}였다.",
                    f"requirement volatility 0.8에서 rework rate 평균은 {round_float(i_vol.loc[0.8, METRICS['rework']])}였다.",
                    f"requirement volatility 0.2에서 scope changes 평균은 {round_float(i_vol.loc[0.2, METRICS['scope']])}였다.",
                    f"requirement volatility 0.8에서 scope changes 평균은 {round_float(i_vol.loc[0.8, METRICS['scope']])}였다.",
                    f"strong PM은 scope changes prevented 평균 {round_float(i_pm.loc['strong_pm', METRICS['scope_prevented']])}로 가장 높았다.",
                    f"strong PM은 rework rate 평균 {round_float(i_pm.loc['strong_pm', METRICS['rework']])}로 가장 낮았다.",
                    f"requirement focused PM은 Change Failure Rate 평균 {round_float(i_pm.loc['requirement_focused_pm', METRICS['cfr']])}%로 가장 낮았다.",
                ],
                "interpretation": [
                    "요구사항 변동성이 커지면 재작업률과 scope change가 함께 증가한다.",
                    "strong PM은 scope change를 더 많이 예방하고 rework rate를 낮추는 방향으로 작동했다.",
                    "requirement focused PM은 CFR 관점에서 강점이 있으나, scope change 예방량은 strong PM보다 낮다.",
                    "Lead Time 평균은 변동성 증가에도 큰 폭으로 증가하지 않았으며, 이는 재작업 증가가 잔여 백로그와 품질 비용에 더 강하게 나타난 결과로 해석된다.",
                ],
            },
        },
    }


def main() -> None:
    setup_matplotlib()
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    data = {sid: load_summary(sid) for sid in "FGHI"}
    figures = {
        "F": {"team_composition": plot_scenario_f(data["F"])},
        "G": {"pm_profile": plot_scenario_g(data["G"])},
        "H": plot_scenario_h(data["H"]),
        "I": plot_scenario_i(data["I"]),
    }
    notes = scenario_notes(data, figures)
    NOTE_PATH.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "report_root": str(REPORT_ROOT),
        "figures": figures,
        "notes": str(NOTE_PATH),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
