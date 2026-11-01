"""Render the figures for the requirement-1 characterization report.

Reads the outputs of scripts/build_health_status.py (data/processed/) and writes
static PNGs to reports/figures/. Style: seaborn theme (Lauren's preference) with the
dataviz skill's validated palette and chrome on top — palette slots 1-2, ink/grid
tokens from the skill's reference instance, validated 2026-11-01
(`validate_palette.js "#2a78d6,#eb6834" --mode light --surface "#fcfcfb"`: all pass).

Usage: python scripts/report_figures.py
"""

from __future__ import annotations

import json
import textwrap

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from oscar_cs.paths import DATA_PROCESSED, FIGURES

STEM = "2026-11-01_health-status-characterization"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"  # categorical slot 1
ORANGE = "#eb6834"  # categorical slot 2


def apply_theme() -> None:
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "grid.color": GRID,
            "axes.edgecolor": AXIS,
            "text.color": INK,
            "axes.labelcolor": INK_2,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.titlecolor": INK,
            "font.size": 11,
            "axes.titlesize": 12.5,
            "figure.dpi": 150,
            "savefig.dpi": 150,
        },
    )


def fig01_top_conditions(conditions: pd.DataFrame, n_members: int) -> None:
    per_condition = (
        conditions.groupby("condition")
        .agg(members_any=("member_id", "nunique"), members_chronic=("chronic", "sum"))
        .sort_values("members_any", ascending=False)
        .head(15)
        .iloc[::-1]  # largest on top after barh
    )

    def wrap_label(name: str) -> str:
        lines = textwrap.wrap(name, width=30)
        if len(lines) > 2:  # re-wrap wider instead of a third line colliding with neighbors
            lines = textwrap.wrap(name, width=40)
        return "\n".join(lines)

    labels = [wrap_label(name) for name in per_condition.index]
    pct_chronic = 100 * per_condition["members_chronic"] / n_members
    pct_acute = 100 * (per_condition["members_any"] - per_condition["members_chronic"]) / n_members

    fig, ax = plt.subplots(figsize=(8.2, 6.6), layout="constrained")
    bar_style = {"height": 0.72, "edgecolor": SURFACE, "linewidth": 1.0}
    ax.barh(
        labels,
        pct_chronic.to_numpy(),
        color=BLUE,
        label="chronic (≥2 claim dates ≥30 days apart)",
        **bar_style,
    )
    ax.barh(
        labels,
        pct_acute.to_numpy(),
        left=pct_chronic.to_numpy(),
        color=ORANGE,
        label="one-off / short episode",
        **bar_style,
    )
    ax.set_title(
        "Respiratory infections touch 1 in 4 members;\nmost flags are one-off, not chronic",
        loc="left",
    )
    ax.set_xlabel(f"% of members with ≥1 claim line (n = {n_members:,})")
    ax.set_ylabel("")
    ax.tick_params(axis="y", labelcolor=INK_2)
    legend = ax.legend(loc="lower right", fontsize=10, frameon=True, framealpha=1.0)
    legend.get_frame().set_facecolor(SURFACE)
    legend.get_frame().set_edgecolor(GRID)
    sns.despine(left=True, bottom=True)
    fig.savefig(FIGURES / f"{STEM}_fig01.png")
    plt.close(fig)


def fig02_conditions_per_member(summary: pd.DataFrame, n_members: int) -> None:
    capped = summary["n_conditions"].clip(upper=15)
    dist = 100 * capped.value_counts().sort_index() / n_members
    labels = [str(i) for i in range(15)] + ["15+"]

    fig, ax = plt.subplots(figsize=(8.2, 4.2), layout="constrained")
    ax.bar(
        dist.index,
        dist.to_numpy(),
        color=BLUE,
        width=0.78,
        edgecolor=SURFACE,
        linewidth=1.0,
    )
    ax.set_xticks(range(16), labels)
    ax.set_title(
        "Most members carry 1–3 distinct conditions; a long multimorbid tail",
        loc="left",
    )
    ax.set_xlabel(
        "distinct CCS level-2 conditions per member\n"
        "(0 = only symptom/administrative or unmapped codes)"
    )
    ax.set_ylabel(f"% of members (n={n_members:,})")
    sns.despine(left=True, bottom=True)
    fig.savefig(FIGURES / f"{STEM}_fig02.png")
    plt.close(fig)


def main() -> int:
    apply_theme()
    conditions = pd.read_parquet(DATA_PROCESSED / "member_conditions.parquet")
    summary = pd.read_parquet(DATA_PROCESSED / "member_health_status.parquet")
    with open(DATA_PROCESSED / "health_status_stats.json") as fh:
        n_members = json.load(fh)["population"]["members_characterized"]
    assert n_members == len(summary)

    FIGURES.mkdir(parents=True, exist_ok=True)
    fig01_top_conditions(conditions, n_members)
    fig02_conditions_per_member(summary, n_members)
    for n in ("fig01", "fig02"):
        print(f"wrote {FIGURES / f'{STEM}_{n}.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
