"""Single-variable frequency distributions: diagnostic codes (one chart), drug classes
(another). Rank-frequency on log-log, annotated with the #1 code and the ranks where
cumulative coverage crosses 50% / 90%. Colors follow the entities (diag=blue, class=aqua).
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

diag = con.execute(
    """
select upper(trim(replace(cl.diag1, '.', ''))) as code,
       coalesce(min(ccs.diag_desc), '(unmapped)') as label, count(*) as n
from claim_lines cl
left join ccs on upper(trim(replace(cl.diag1, '.', ''))) = ccs.diag
where try_cast(cl.date_svc as date) between $ws and $we
group by 1 order by n desc
""",
    W,
).df()

cls = con.execute(
    """
select drug_class as code, drug_class as label, count(*) as n
from prescription_drugs
where try_cast(date_svc as date) between $ws and $we
group by 1 order by n desc
""",
    W,
).df()


def plot_one(frame, color, title, unit, fname, top_label):
    counts = frame["n"].to_numpy()
    total = counts.sum()
    cum = 100 * np.cumsum(counts) / total
    k50, k90 = int(np.searchsorted(cum, 50) + 1), int(np.searchsorted(cum, 90) + 1)
    ranks = np.arange(1, len(counts) + 1)

    fig, ax = plt.subplots(figsize=(7.8, 4.8), layout="constrained")
    ax.plot(ranks, counts, color=color, lw=2.5)
    ax.fill_between(ranks, counts, 1, color=color, alpha=0.12, lw=0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(bottom=0.8)

    ax.annotate(
        f"#1: {top_label}\n{counts[0]:,} {unit}",
        xy=(1, counts[0]),
        xytext=(2.2, counts[0] * 0.12),
        color=INK_2,
        arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 1},
    )
    for k, share in ((k50, "50%"), (k90, "90%")):
        y = counts[k - 1]
        ax.plot(
            [k], [y], marker="o", ms=7, color=color, markeredgecolor=SURFACE, markeredgewidth=1.5
        )
        ax.annotate(
            f"top {k:,} codes\n= {share} of {unit}",
            xy=(k, y),
            xytext=(k * 1.6, y * 2.6),
            color=INK_2,
            arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 1},
        )

    ax.set_title(title, loc="left")
    ax.set_xlabel(f"code rank, most to least used (log; {len(counts):,} distinct)")
    ax.set_ylabel(f"{unit} carrying the code (log)")
    sns.despine(left=True, bottom=True)
    fig.savefig(OUT / ("2026-11-02_eda-session_" + fname))
    plt.close(fig)
    print(f"{fname}: #1={top_label} ({counts[0]:,}) | 50% at top {k50:,} | 90% at top {k90:,}")


diag_top = f"{diag.iloc[0]['code']} — {diag.iloc[0]['label'][:38]}"
plot_one(
    diag,
    BLUE,
    "Diagnostic codes: half of all claim rows come from\n"
    "a small head, then a tail of thousands of rare codes",
    "claim rows",
    "freq_diag_codes.png",
    diag_top,
)

cls_top = cls.iloc[0]["label"][:38]
plot_one(
    cls,
    AQUA,
    "Drug classes: the same heavy-headed shape,\nbut the whole vocabulary is only hundreds deep",
    "fills",
    "freq_drug_classes.png",
    cls_top,
)
