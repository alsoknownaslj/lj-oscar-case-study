"""Probability-distribution view of member utilization volumes + outlier handling.

A. empirical distributions of dx claim lines / rx fills per member (CCDF figures,
   quantile table)
B. outlier diagnostics: IQR fences (raw + log) vs percentile tails; cross-tail overlap
C. quantile-based contingency (quartile bins, ties kept together) and a decile x decile
   dependence heatmap: joint probability vs independence (lift), both-table members.
"""

import warnings

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from oscar_cs.db import connect_views
from oscar_cs.health_status import ANALYSIS_WINDOW_END, ANALYSIS_WINDOW_START
from oscar_cs.paths import FIGURES

warnings.filterwarnings("ignore", category=FutureWarning)
OUT = FIGURES
SURFACE, INK, INK_2, MUTED, GRID, AXIS = (
    "#fcfcfb",
    "#0b0b0b",
    "#52514e",
    "#898781",
    "#e1e0d9",
    "#c3c2b7",
)
BLUE, AQUA, RED, MID = "#2a78d6", "#1baf7a", "#e34948", "#f0efec"

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
dx = con.execute(
    """
select member_id, count(*) as v from claim_lines
where try_cast(date_svc as date) between $ws and $we group by 1""",
    W,
).df()
rx = con.execute(
    """
select member_id, count(*) as v from prescription_drugs
where try_cast(date_svc as date) between $ws and $we group by 1""",
    W,
).df()

QS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 0.999]
print("### A. quantiles of per-member volume (in-window)")
print("q | dx claim lines | rx fills")
for q in QS:
    print(f"p{q * 100:g} | {dx['v'].quantile(q):.0f} | {rx['v'].quantile(q):.0f}")
print(f"max | {dx['v'].max():,} | {rx['v'].max():,}")
print(f"n | {len(dx):,} | {len(rx):,}")

print("\n### B. outlier diagnostics")
for name, s in (("dx lines", dx["v"]), ("rx fills", rx["v"])):
    q1, q3 = s.quantile([0.25, 0.75])
    fence = q3 + 1.5 * (q3 - q1)
    lg = np.log(s)
    lq1, lq3 = lg.quantile([0.25, 0.75])
    lfence = float(np.exp(lq3 + 1.5 * (lq3 - lq1)))
    print(
        f"{name}: IQR fence(raw) = {fence:.0f} -> flags "
        f"{(100 * (s > fence).mean()):.1f}% of members; "
        f"IQR fence(log) = {lfence:.0f} -> flags {(100 * (s > lfence).mean()):.2f}%; "
        f">p99 = {(s > s.quantile(0.99)).sum():,} members; "
        f">p99.9 = {(s > s.quantile(0.999)).sum():,}"
    )
both = dx.merge(rx, on="member_id", suffixes=("_dx", "_rx"))
t_dx, t_rx = dx["v"].quantile(0.99), rx["v"].quantile(0.99)
top_both = ((both["v_dx"] > t_dx) & (both["v_rx"] > t_rx)).sum()
exp_both = len(both) * (dx["v"] > t_dx).mean() * (rx["v"] > t_rx).mean()
print(f"members above p99 on BOTH axes: {top_both:,} (independence would predict ~{exp_both:.0f})")

# ---- CCDF figures -----------------------------------------------------------------
for s, color, name, unit, fname in (
    (dx["v"], BLUE, "Diagnostic claim lines per member", "claim lines", "prob_dx_ccdf.png"),
    (rx["v"], AQUA, "Fills per member", "fills", "prob_rx_ccdf.png"),
):
    vals = np.sort(s.to_numpy())
    uvals, first = np.unique(vals, return_index=True)
    p = 1.0 - first / len(vals)
    fig, ax = plt.subplots(figsize=(7.6, 4.6), layout="constrained")
    ax.plot(uvals, p, color=color, lw=2.5)
    ax.set_xscale("log")
    ax.set_yscale("log")
    for q, lbl in ((0.5, "p50"), (0.9, "p90"), (0.99, "p99"), (0.999, "p99.9")):
        xq = s.quantile(q)
        yq = p[np.searchsorted(uvals, xq, side="right") - 1]
        ax.plot([xq], [yq], "o", ms=7, color=color, markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.annotate(
            f"{lbl}: {xq:.0f}",
            xy=(xq, yq),
            xytext=(xq * 1.5, yq * 1.8),
            color=INK_2,
            fontsize=9,
            arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 1},
        )
    ax.set_title(f"{name}: the actual distribution, tail and all", loc="left")
    ax.set_xlabel(f"x = {unit} in window (log)")
    ax.set_ylabel("P(member ≥ x)  (log)")
    sns.despine(left=True, bottom=True)
    fig.savefig(OUT / ("2026-11-02_eda-session_" + fname))
    plt.close(fig)


# ---- C. quartile-bin contingency ---------------------------------------------------
def qbin(s, probs=(0.25, 0.50, 0.75)):
    cuts = np.unique(s.quantile(list(probs)).to_numpy())
    idx = np.searchsorted(cuts, s.to_numpy(), side="left")
    labels = []
    lo = s.min()
    for c in list(cuts) + [s.max()]:
        labels.append(f"{lo:.0f}–{c:.0f}" if c > lo else f"{lo:.0f}")
        lo = c + 1
    return idx, [f"Q{i + 1} [{t}]" for i, t in enumerate(labels)]


dx["bin"], dx_labels = qbin(dx["v"])
rx["bin"], rx_labels = qbin(rx["v"])
univ = dx[["member_id", "bin"]].merge(
    rx[["member_id", "bin"]], on="member_id", how="outer", suffixes=("_dx", "_rx")
)
dx_names = ["none"] + dx_labels
rx_names = ["none"] + rx_labels
univ["dxq"] = univ["bin_dx"].map(lambda b: dx_names[int(b) + 1] if pd.notna(b) else "none")
univ["rxq"] = univ["bin_rx"].map(lambda b: rx_names[int(b) + 1] if pd.notna(b) else "none")
ct = pd.crosstab(univ["dxq"], univ["rxq"]).reindex(index=dx_names, columns=rx_names, fill_value=0)
n = len(univ)
print(f"\n### C. quartile-bin contingency (% of union {n:,}); bins carry value ranges")
print((100 * ct / n).round(1).to_string())
print("\nrow % (where each dx quartile lands on rx):")
print((100 * ct.div(ct.sum(axis=1), axis=0)).round(1).to_string())
print("\nactual marginal shares (ties make quartiles unequal):")
print("dx:", (100 * univ["dxq"].value_counts(normalize=True)[dx_names]).round(1).to_dict())
print("rx:", (100 * univ["rxq"].value_counts(normalize=True)[rx_names]).round(1).to_dict())


# ---- decile x decile dependence heatmap (both-table members) ------------------------
def dbin(s):
    cuts = np.unique(s.quantile(np.arange(0.1, 1.0, 0.1)).to_numpy())
    return np.searchsorted(cuts, s.to_numpy(), side="left"), cuts


bdx, cuts_dx = dbin(both["v_dx"])
brx, cuts_rx = dbin(both["v_rx"])
joint = pd.crosstab(bdx, brx).to_numpy().astype(float)
pj = joint / joint.sum()
pr, pc = pj.sum(axis=1, keepdims=True), pj.sum(axis=0, keepdims=True)
lift = pj / (pr @ pc)
loglift = np.log2(np.clip(lift, 2**-2.5, 2**2.5))


def edge_labels(cuts, vmax):
    lo, out = 1, []
    for c in list(cuts) + [vmax]:
        out.append(f"{lo:.0f}" if c <= lo else f"{lo:.0f}–{c:.0f}")
        lo = c + 1
    return out


xl = edge_labels(cuts_rx, both["v_rx"].max())
yl = edge_labels(cuts_dx, both["v_dx"].max())
cmap = mcolors.LinearSegmentedColormap.from_list("div", [RED, MID, BLUE])
fig, ax = plt.subplots(figsize=(8.6, 6.8), layout="constrained")
mesh = ax.pcolormesh(
    loglift, cmap=cmap, norm=mcolors.TwoSlopeNorm(0, -2.5, 2.5), edgecolors=SURFACE, linewidth=1.2
)
ax.set_xticks(np.arange(len(xl)) + 0.5, xl, fontsize=8.5)
ax.set_yticks(np.arange(len(yl)) + 0.5, yl, fontsize=8.5)
ax.set_xlabel("rx fills per member (decile bins, ties merged)")
ax.set_ylabel("dx claim lines per member (decile bins)")
for i in range(loglift.shape[0]):
    for j in range(loglift.shape[1]):
        v = loglift[i, j]
        if abs(v) >= 1:
            ax.text(
                j + 0.5,
                i + 0.5,
                f"{2**v:.1f}×",
                ha="center",
                va="center",
                fontsize=7.5,
                color="#ffffff" if abs(v) >= 1.8 else INK,
            )
ax.set_title(
    "Joint distribution vs independence: heavy users cluster,\n"
    "light-dx members avoid heavy rx (both-table members)",
    loc="left",
)
cb = fig.colorbar(mesh, ax=ax, shrink=0.8, ticks=[-2, -1, 0, 1, 2])
cb.ax.set_yticklabels(["1/4×", "1/2×", "1×", "2×", "4×"])
cb.set_label("P(cell) / independence", color=INK_2)
ax.grid(False)
fig.savefig(OUT / "2026-11-02_eda-session_prob_joint_lift.png")
plt.close(fig)
print(
    f"\nheatmap bins: dx {loglift.shape[0]} x rx {loglift.shape[1]} "
    f"(ties merged some deciles); corner lifts: "
    f"low-low {lift[0, 0]:.2f}x, low-high {lift[0, -1]:.2f}x, "
    f"high-low {lift[-1, 0]:.2f}x, high-high {lift[-1, -1]:.2f}x"
)
print("figures written")
