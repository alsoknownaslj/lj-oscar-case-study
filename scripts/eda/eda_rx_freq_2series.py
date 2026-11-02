"""fig1/fig2 variant: drug classes vs NDCs only (diagnosis series dropped).

Colors stay with their entities from the 3-series version (no repaint on filter):
NDCs = orange (slot 2), drug classes = aqua (slot 3).
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
ORANGE, AQUA = "#eb6834", "#1baf7a"

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
con.execute(
    """
create temp table rx as
select ndc, drug_class from prescription_drugs
where try_cast(date_svc as date) between $ws and $we
""",
    {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END},
)

freq = {
    "NDCs": con.execute("select count(*) as n from rx group by ndc order by n desc")
    .df()["n"]
    .to_numpy(),
    "drug classes": con.execute("select count(*) as n from rx group by drug_class order by n desc")
    .df()["n"]
    .to_numpy(),
}
colors = {"NDCs": ORANGE, "drug classes": AQUA}

cum = {k: 100 * np.cumsum(v) / v.sum() for k, v in freq.items()}
k87 = int(np.searchsorted(cum["NDCs"], 87) + 1)
k_cls_87 = int(np.searchsorted(cum["drug classes"], 87) + 1)
print(f"NDCs: {len(freq['NDCs']):,} distinct; to reach 87% of fills: top {k87:,}")
print(f"classes: {len(freq['drug classes']):,} distinct; to reach 87%: top {k_cls_87:,}")
for k in (10, 100, 1000):
    print(
        f"top {k}: classes {cum['drug classes'][min(k, len(cum['drug classes'])) - 1]:.0f}% "
        f"| NDCs {cum['NDCs'][k - 1]:.0f}%"
    )

fig, ax = plt.subplots(figsize=(7.8, 4.6), layout="constrained")
for name, arr in freq.items():
    ax.plot(np.arange(1, len(arr) + 1), arr, color=colors[name], lw=2, label=name)
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_title(
    "Same fills, two vocabularies: classes concentrate\nwhat NDCs scatter across 20k product codes",
    loc="left",
)
ax.set_xlabel("code rank (log)")
ax.set_ylabel("fills carrying the code (log)")
leg = ax.legend(frameon=True, framealpha=1.0)
leg.get_frame().set_facecolor(SURFACE)
leg.get_frame().set_edgecolor(GRID)
sns.despine(left=True, bottom=True)
fig.savefig(OUT / "2026-11-02_eda-session_rx_fig01b_rank_frequency_2series.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.8, 4.6), layout="constrained")
for name, arr in freq.items():
    ax.plot(np.arange(1, len(arr) + 1), cum[name], color=colors[name], lw=2, label=name)
ax.axhline(87, color=AXIS, lw=1, ls=":")
ax.annotate(
    f"87% of fills:\ntop {k_cls_87} classes vs top {k87:,} NDCs",
    xy=(k_cls_87, 87),
    xytext=(220, 55),
    color=INK_2,
    arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 1},
)
ax.set_xscale("log")
ax.set_title(f"Coverage: {k_cls_87} drug classes do what {k87:,} NDCs do", loc="left")
ax.set_xlabel("top k codes (log)")
ax.set_ylabel("cumulative % of fills")
ax.set_ylim(0, 102)
leg = ax.legend(loc="lower right", frameon=True, framealpha=1.0)
leg.get_frame().set_facecolor(SURFACE)
leg.get_frame().set_edgecolor(GRID)
sns.despine(left=True, bottom=True)
fig.savefig(OUT / "2026-11-02_eda-session_rx_fig02b_cumulative_coverage_2series.png")
plt.close(fig)
print("wrote figures")
