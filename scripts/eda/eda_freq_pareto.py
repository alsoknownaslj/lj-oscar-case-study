"""Pareto view of code frequencies: linear rank on x, per-code count on the left y,
cumulative % of volume on the right y. One chart per variable (diag codes, drug classes).
Cumulative line wears neutral ink (it is a transform of the same data, not a new entity).
"""

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from oscar_cs.db import connect_views
from oscar_cs.health_status import ANALYSIS_WINDOW_END, ANALYSIS_WINDOW_START
from oscar_cs.paths import FIGURES

OUT = FIGURES
SURFACE, INK, INK_2, MUTED, GRID, AXIS = (
    "#fcfcfb",
    "#0b0b0b",
    "#52514e",
    "#898781",
    "#e1e0d9",
    "#c3c2b7",
)
BLUE, AQUA = "#2a78d6", "#1baf7a"

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

con = connect_views()
W = {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END}
diag_counts = (
    con.execute(
        """
select count(*) as n from claim_lines
where try_cast(date_svc as date) between $ws and $we
group by upper(trim(replace(diag1, '.', ''))) order by n desc
""",
        W,
    )
    .df()["n"]
    .to_numpy()
)
cls_counts = (
    con.execute(
        """
select count(*) as n from prescription_drugs
where try_cast(date_svc as date) between $ws and $we
group by drug_class order by n desc
""",
        W,
    )
    .df()["n"]
    .to_numpy()
)


def pareto(counts, color, title, unit, fname):
    ranks = np.arange(1, len(counts) + 1)
    cum = 100 * np.cumsum(counts) / counts.sum()
    k50, k90 = int(np.searchsorted(cum, 50) + 1), int(np.searchsorted(cum, 90) + 1)

    fig, ax = plt.subplots(figsize=(7.8, 4.8), layout="constrained")
    ax.fill_between(ranks, counts, 0, color=color, alpha=0.25, lw=0)
    ax.plot(ranks, counts, color=color, lw=2, label=f"{unit} per code")
    ax.set_xlim(0, len(counts))
    ax.set_ylim(0, counts[0] * 1.05)
    ax.set_xlabel(f"code rank, most to least used (linear; {len(counts):,} distinct)")
    ax.set_ylabel(f"{unit} carrying the code")

    ax2 = ax.twinx()
    ax2.grid(False)
    ax2.plot(ranks, cum, color=INK_2, lw=2, label="cumulative %")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("cumulative % of " + unit, color=INK_2)
    ax2.tick_params(axis="y", labelcolor=INK_2)
    for k, share in ((k50, "50%"), (k90, "90%")):
        ax2.plot(
            [k],
            [cum[k - 1]],
            marker="o",
            ms=7,
            color=INK_2,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
        )
        ax2.annotate(
            f"top {k:,} = {share}",
            xy=(k, cum[k - 1]),
            xytext=(k + len(counts) * 0.05, cum[k - 1] - 14),
            color=INK_2,
            arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 1},
        )

    lines = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    leg = ax.legend(lines, labels, loc="center right", frameon=True, framealpha=1.0)
    leg.get_frame().set_facecolor(SURFACE)
    leg.get_frame().set_edgecolor(GRID)

    ax.set_title(title, loc="left")
    sns.despine(ax=ax, left=True, bottom=True)
    sns.despine(ax=ax2, left=True, right=True, bottom=True)
    fig.savefig(OUT / ("2026-11-02_eda-session_" + fname))
    plt.close(fig)
    print(f"{fname}: 50% at {k50:,} | 90% at {k90:,} | axis length {len(counts):,}")


pareto(
    diag_counts,
    BLUE,
    "Diagnostic codes on a linear axis: the head is a sliver,\n"
    "and 7/8 of the axis is codes carrying the last 10% of rows",
    "claim rows",
    "pareto_diag_codes.png",
)
pareto(
    cls_counts,
    AQUA,
    "Drug classes on a linear axis: the bend is actually visible\n"
    "when the vocabulary is only 669 deep",
    "fills",
    "pareto_drug_classes.png",
)
