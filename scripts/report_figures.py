"""Render the figures for the final case-study report (health status v2).

Reads the outputs of scripts/build_health_status.py (data/processed/) and writes
static PNGs to reports/figures/. Style: seaborn theme (Lauren's preference) with the
dataviz skill's validated palette and chrome on top — palette slots 1-2, ink/grid
tokens from the skill's reference instance, validated 2026-11-01
(`validate_palette.js "#2a78d6,#eb6834" --mode light --surface "#fcfcfb"`: all pass).

Usage: python scripts/report_figures.py  (after build_health_status.py)
"""

from __future__ import annotations

import json
import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

from oscar_cs.paths import DATA_PROCESSED, FIGURES

STEM = "2026-11-02_final"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"  # categorical slot 1 — chronic
ORANGE = "#eb6834"  # categorical slot 2 — episode
GRAY = "#c3c2b7"  # de-emphasized — one-off

TIER_ORDER = ["none", "low", "med", "high"]
SHAPES = [("chronic", BLUE), ("episode", ORANGE), ("one_off", GRAY)]


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
    """Top 15 conditions by members, stacked by v2 shape."""
    per = (
        conditions.pivot_table(
            index="condition", columns="shape", values="member_id", aggfunc="nunique"
        )
        .reindex(columns=[s for s, _ in SHAPES])
        .fillna(0)
        .astype(int)
    )
    per["members_any"] = per.sum(axis=1)
    top = per.sort_values("members_any", ascending=True).tail(15)
    labels = [textwrap.shorten(c, width=44, placeholder="…") for c in top.index]

    fig, ax = plt.subplots(figsize=(9.2, 6.4))
    left = np.zeros(len(top))
    for shape, color in SHAPES:
        ax.barh(labels, top[shape], left=left, color=color, label=shape.replace("_", "-"))
        left += top[shape].to_numpy()
    for y, total in enumerate(top["members_any"]):
        ax.annotate(
            f"{100 * total / n_members:.0f}%",
            (total, y),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=INK_2,
        )
    ax.set_xlim(0, top["members_any"].max() * 1.09)
    ax.set_xlabel("members with the condition (right label: share of 245,151)")
    ax.set_title("Top 15 conditions by members, split by shape", loc="left", pad=12)
    ax.legend(frameon=False, loc="lower right", title=None)
    sns.despine(left=True, bottom=True)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{STEM}_fig01_top_conditions.png")
    plt.close(fig)


def fig02_tier_lift(stats: dict) -> None:
    """Dx x rx tier contingency: lift vs independence, member counts annotated."""
    lift = pd.DataFrame(stats["tiers"]["contingency_lift"]).T.reindex(
        index=TIER_ORDER, columns=TIER_ORDER
    )
    members = pd.DataFrame(stats["tiers"]["contingency_members"]).T.reindex(
        index=TIER_ORDER, columns=TIER_ORDER
    )
    log_lift = np.log2(lift.where(lift > 0)).clip(-3, 3)
    cmap = LinearSegmentedColormap.from_list("div", [BLUE, SURFACE, ORANGE])

    fig, ax = plt.subplots(figsize=(7.4, 5.8))
    sns.heatmap(
        log_lift,
        cmap=cmap,
        center=0,
        vmin=-3,
        vmax=3,
        linewidths=1.2,
        linecolor=SURFACE,
        cbar_kws={"label": "log2 lift vs independence", "shrink": 0.85},
        ax=ax,
    )
    for i, row in enumerate(TIER_ORDER):
        for j, col in enumerate(TIER_ORDER):
            n = int(members.loc[row, col])
            text = "—" if n == 0 else f"{lift.loc[row, col]:.2f}×\n{n:,}"
            ax.text(j + 0.5, i + 0.5, text, ha="center", va="center", fontsize=9.5, color=INK)
    ax.set_xlabel("rx fill tier (head/tail breaks)")
    ax.set_ylabel("diagnostic-line tier")
    ax.set_title(
        "Members concentrate on the tier diagonal (lift ×, member count)", loc="left", pad=12
    )
    fig.tight_layout()
    fig.savefig(FIGURES / f"{STEM}_fig02_tier_lift.png")
    plt.close(fig)


def main() -> int:
    apply_theme()
    FIGURES.mkdir(parents=True, exist_ok=True)
    conditions = pd.read_parquet(DATA_PROCESSED / "member_conditions.parquet")
    with open(DATA_PROCESSED / "health_status_stats.json") as fh:
        stats = json.load(fh)
    n_members = stats["population"]["members_characterized"]
    fig01_top_conditions(conditions, n_members)
    fig02_tier_lift(stats)
    print(f"wrote 2 figures to {FIGURES} (stem {STEM})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
