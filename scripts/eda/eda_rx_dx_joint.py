"""Rx distributions + the first joint claims-rx view. Canonical window throughout.

A. drug classes: fills, members, fills/member (top by fills)
B. refill buckets per member x class pair: 1-2 / 3-4 / 5+ fills, per class
C. member tiers by the median: distinct L2 conditions (claims side) and distinct drug
   classes (rx side); none = absent from that table in-window. Contingency + Spearman.
D. condition x class co-occurrence LIFT heatmap, hierarchically cluster-ordered;
   Fractures / Mood disorders / Diabetes rows forced in to test the asymmetry hypothesis.
"""

import textwrap

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.cluster import hierarchy
from scipy.stats import spearmanr

from oscar_cs.db import connect_views
from oscar_cs.health_status import (
    ANALYSIS_WINDOW_END,
    ANALYSIS_WINDOW_START,
    NON_CONDITION_CHAPTERS,
)
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
BLUE, RED, MID = "#2a78d6", "#e34948", "#f0efec"  # diverging pair + neutral midpoint

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
excl = ", ".join(f"'{c}'" for c in NON_CONDITION_CHAPTERS)
W = {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END}
con.execute(
    """
create temp table rx as
select member_id, drug_class, try_cast(date_svc as date) as fd
from prescription_drugs where try_cast(date_svc as date) between $ws and $we
""",
    W,
)
con.execute(
    f"""
create temp table dx as
select distinct cl.member_id,
    regexp_replace(ccs.ccs_2_desc, '\\s*\\[[^\\]]*\\]\\s*$', '') as cat,
    try_cast(cl.date_svc as date) as d
from claim_lines cl
join ccs on upper(trim(replace(cl.diag1, '.', ''))) = ccs.diag
where try_cast(cl.date_svc as date) between $ws and $we
  and ccs.ccs_1_desc not in ({excl})
""",
    W,
)
con.execute(
    """
create temp table claims_members as
select distinct member_id from claim_lines
where try_cast(date_svc as date) between $ws and $we
""",
    W,
)

# ---- A. class table ---------------------------------------------------------------
print("### A. top drug classes by fills (canonical window)")
cls_tbl = con.execute("""
select drug_class, count(*) as fills, count(distinct member_id) as members,
    round(count(*) * 1.0 / count(distinct member_id), 1) as fills_per_member
from rx group by 1 order by fills desc limit 15
""").df()
med_fills = (
    con.execute("""
select drug_class, median(n) as med from (
    select drug_class, member_id, count(*) as n from rx group by 1, 2
) group by 1
""")
    .df()
    .set_index("drug_class")["med"]
)
cls_tbl["median_fills_per_member"] = cls_tbl["drug_class"].map(med_fills)
print(cls_tbl.to_string(index=False))

# ---- B. refill buckets per member x class -----------------------------------------
pair_fills = con.execute("select drug_class, member_id, count(*) as n from rx group by 1, 2").df()
pair_fills["bucket"] = pd.cut(
    pair_fills["n"], [0, 2, 4, np.inf], labels=["1-2 fills", "3-4 fills", "5+ fills"]
)
overall = (100 * pair_fills["bucket"].value_counts(normalize=True)).round(1)
print(f"\n### B. refill buckets, all {len(pair_fills):,} member x class pairs:")
print(overall.to_dict())
top_classes = (
    con.execute("""
select drug_class from rx group by 1 order by count(distinct member_id) desc limit 15
""")
    .df()["drug_class"]
    .tolist()
)
bucket_tbl = pair_fills[pair_fills["drug_class"].isin(top_classes)].pivot_table(
    index="drug_class", columns="bucket", values="n", aggfunc="count", fill_value=0, observed=True
)
bucket_pct = (100 * bucket_tbl.div(bucket_tbl.sum(axis=1), axis=0)).round(1)
bucket_pct["members"] = bucket_tbl.sum(axis=1)
bucket_pct = bucket_pct.sort_values("5+ fills", ascending=False)
print("\ntop-15 classes by members, sorted by % of members with 5+ fills:")
print(bucket_pct.to_string())

# ---- C. tiers + contingency -------------------------------------------------------
n_cond = con.execute("select member_id, count(distinct cat) as n from dx group by 1").df()
n_cls = con.execute("select member_id, count(distinct drug_class) as n from rx group by 1").df()
claims_m = con.execute("select member_id from claims_members").df()
claims_side = claims_m.merge(n_cond, on="member_id", how="left").fillna({"n": 0})
med_dx = claims_side["n"].median()
med_rx = n_cls["n"].median()
print(
    f"\n### C. tiers: median distinct L2 conditions per claims member = {med_dx:.0f}; "
    f"median distinct classes per rx member = {med_rx:.0f}"
)


def tier(series, med):
    return np.select([series < med, series == med], ["low", "mid"], default="high")


claims_side["dx_tier"] = tier(claims_side["n"], med_dx)
n_cls["rx_tier"] = tier(n_cls["n"], med_rx)
univ = claims_side[["member_id", "dx_tier"]].merge(
    n_cls[["member_id", "rx_tier"]], on="member_id", how="outer"
)
univ["dx_tier"] = univ["dx_tier"].fillna("none (no claims)")
univ["rx_tier"] = univ["rx_tier"].fillna("none (no fills)")
order_dx = ["none (no claims)", "low", "mid", "high"]
order_rx = ["none (no fills)", "low", "mid", "high"]
ct = pd.crosstab(univ["dx_tier"], univ["rx_tier"]).reindex(index=order_dx, columns=order_rx)
print(
    f"\ncontingency (counts; union = {len(univ):,} in-window members); "
    f"dx tier = rows, rx tier = cols"
)
print(ct.to_string())
ct_pct = (100 * ct / len(univ)).round(1)
print("\nsame, % of union:")
print(ct_pct.to_string())
both = univ.merge(claims_side[["member_id", "n"]], on="member_id").merge(
    n_cls[["member_id", "n"]], on="member_id", suffixes=("_dx", "_rx")
)
rho, _ = spearmanr(both["n_dx"], both["n_rx"])
print(
    f"\nSpearman rho (distinct conditions vs distinct classes, "
    f"both-table members n={len(both):,}): {rho:.3f}"
)

# ---- D. condition x class lift heatmap --------------------------------------------
both_ids = con.execute("""
select member_id from claims_members
intersect select distinct member_id from rx
""").df()["member_id"]
N = len(both_ids)
cond_top = (
    con.execute(
        """
select cat from dx where member_id in (select member_id from (select unnest($ids) as member_id))
group by 1 order by count(distinct member_id) desc limit 12
""",
        {"ids": both_ids.tolist()},
    )
    .df()["cat"]
    .tolist()
)
for forced in ("Fractures", "Mood disorders", "Diabetes mellitus without complication"):
    if forced not in cond_top:
        cond_top.append(forced)

con.execute(
    "create temp table both_ids as select unnest($ids) as member_id", {"ids": both_ids.tolist()}
)
cond_sets = con.execute(f"""
select cat, member_id from dx
where cat in ({", ".join(f"'{c}'" for c in cond_top)})
  and member_id in (select member_id from both_ids) group by 1, 2
""").df()
cond_members = cond_sets.groupby("cat")["member_id"].apply(set)

# classes: for each condition pick the max-lift class (>=5k members), then union
cls_members_all = con.execute("""
select drug_class, member_id from rx
where member_id in (select member_id from both_ids) group by 1, 2
""").df()
cls_counts = cls_members_all.groupby("drug_class")["member_id"].nunique()
big_classes = cls_counts[cls_counts >= 5000].index
cls_sets = {
    c: set(g)
    for c, g in cls_members_all[cls_members_all["drug_class"].isin(big_classes)].groupby(
        "drug_class"
    )["member_id"]
}
picked: list[str] = []
for cat in cond_top:
    cm = cond_members[cat]
    lifts = {c: (len(cm & s) / len(cm)) / (len(s) / N) for c, s in cls_sets.items()}
    best = max(lifts, key=lifts.get)
    if best not in picked:
        picked.append(best)
picked = picked[:14]

lift = pd.DataFrame(index=cond_top, columns=picked, dtype=float)
for cat in cond_top:
    cm = cond_members[cat]
    for c in picked:
        s = cls_sets[c]
        lift.loc[cat, c] = (len(cm & s) / len(cm)) / (len(s) / N)
log_lift = np.log2(lift.astype(float).clip(lower=2**-4, upper=2**4))

row_order = hierarchy.leaves_list(hierarchy.linkage(log_lift, method="average"))
col_order = hierarchy.leaves_list(hierarchy.linkage(log_lift.T, method="average"))
ll = log_lift.iloc[row_order, col_order]

cmap = mcolors.LinearSegmentedColormap.from_list("div", [RED, MID, BLUE])
fig, ax = plt.subplots(figsize=(9.6, 7.6), layout="constrained")
mesh = ax.pcolormesh(
    ll.to_numpy(), cmap=cmap, norm=mcolors.TwoSlopeNorm(0, -4, 4), edgecolors=SURFACE, linewidth=1.2
)
ax.set_xticks(
    np.arange(len(ll.columns)) + 0.5,
    ["\n".join(textwrap.wrap(c, 18)) for c in ll.columns],
    rotation=45,
    ha="right",
    fontsize=8,
)
ax.set_yticks(
    np.arange(len(ll.index)) + 0.5, ["\n".join(textwrap.wrap(c, 26)) for c in ll.index], fontsize=8
)
for i in range(ll.shape[0]):
    for j in range(ll.shape[1]):
        v = ll.iloc[i, j]
        if abs(v) >= 2:
            ax.text(
                j + 0.5,
                i + 0.5,
                f"{2**v:.0f}×",
                ha="center",
                va="center",
                fontsize=7.5,
                color="#ffffff" if abs(v) >= 2.6 else INK,
            )
ax.set_title(
    "Drugs find their diseases: condition × drug-class lift\n"
    "(both-table members in window; cluster-ordered; labels where lift ≥4× or ≤0.25×)",
    loc="left",
)
cb = fig.colorbar(mesh, ax=ax, shrink=0.75, ticks=[-4, -2, 0, 2, 4])
cb.ax.set_yticklabels(["1/16×", "1/4×", "1×", "4×", "16×"])
cb.set_label("lift vs independence", color=INK_2)
ax.grid(False)
fig.savefig(OUT / "2026-11-02_eda-session_joint_fig_lift_heatmap.png")
plt.close(fig)
print(f"\nheatmap: {ll.shape[0]} conditions x {ll.shape[1]} classes, N={N:,} both-table members")
print(
    "max lift cell:",
    lift.melt(ignore_index=False).set_index("variable", append=True)["value"].idxmax(),
    f"{lift.to_numpy().max():.1f}x",
)
