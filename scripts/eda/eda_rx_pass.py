"""Rx-table EDA pass inside the canonical window + code-frequency plots.

Prints: fills/member stats, top categories/groups/classes by members, persistence
(member x drug_class refill structure, inter-fill gaps). Renders 4 figures to the
scratchpad: rank-frequency (log-log), cumulative coverage, fills/member, inter-fill gaps.
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
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"  # validated slots 1-3

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
con.execute(
    """
create temp table rx as
select member_id, try_cast(date_svc as date) as fd, ndc,
       drug_category, drug_group, drug_class
from prescription_drugs
where try_cast(date_svc as date) between $ws and $we
""",
    W,
)
con.execute(
    """
create temp table cl as
select member_id, upper(trim(replace(diag1, '.', ''))) as dn
from claim_lines
where try_cast(date_svc as date) between $ws and $we
""",
    W,
)

print("=== A. fills per member (in-window rx members) ===")
per_m = con.execute("""
select count(*) as fills, count(distinct fd) as fill_days,
       count(distinct drug_class) as classes
from rx group by member_id
""").df()
n_rx_members = len(per_m)
for col in ("fills", "fill_days", "classes"):
    q = per_m[col].quantile([0.25, 0.5, 0.75, 0.9, 0.99]).tolist()
    print(
        f"{col:>9}: p25={q[0]:.0f} med={q[1]:.0f} p75={q[2]:.0f} p90={q[3]:.0f} "
        f"p99={q[4]:.0f} max={per_m[col].max():,} mean={per_m[col].mean():.1f}"
    )
print(f"members: {n_rx_members:,}")

print("\n=== B. hierarchy usage in window ===")
print(
    con.execute("""
select count(distinct drug_category), count(distinct drug_group),
       count(distinct drug_class), count(distinct ndc) from rx""").fetchone(),
    "= categories, groups, classes, NDCs observed (of 90/477/684/21,400)",
)
for lvl, topn in (("drug_category", 12), ("drug_group", 8), ("drug_class", 8)):
    rows = con.execute(f"""
        select {lvl}, count(distinct member_id) as m, count(*) as f
        from rx group by 1 order by m desc limit {topn}""").fetchall()
    print(f"\ntop {topn} {lvl} by members (% of {n_rx_members:,}):")
    for r in rows:
        print(f"  {r[0][:52]:<52} {r[1]:>8,} ({100 * r[1] / n_rx_members:4.1f}%) {r[2]:>9,} fills")

print("\n=== C. persistence: member x drug_class pairs ===")
pairs = con.execute("""
select count(*) as pairs,
    round(100.0 * avg(case when n_fills = 1 then 1 else 0 end), 1) as pct_single,
    round(100.0 * avg(case when n_fills = 2 then 1 else 0 end), 1) as pct_two,
    round(100.0 * avg(case when n_fills >= 3 then 1 else 0 end), 1) as pct_3plus,
    round(100.0 * avg(case when n_fills >= 3 and span >= 90 then 1 else 0 end), 1)
        as pct_sustained
from (select member_id, drug_class, count(*) as n_fills,
             date_diff('day', min(fd), max(fd)) as span
      from rx group by 1, 2)
""").fetchone()
print(
    f"pairs: {pairs[0]:,} | single-fill {pairs[1]}% | two {pairs[2]}% | 3+ {pairs[3]}% "
    f"| sustained (>=3 fills, span>=90d): {pairs[4]}%"
)
(mem_sust,) = con.execute("""
select count(distinct member_id) from (
  select member_id, drug_class from rx group by 1, 2
  having count(*) >= 3 and date_diff('day', min(fd), max(fd)) >= 90)
""").fetchone()
print(f"members with >=1 sustained class: {mem_sust:,} ({100 * mem_sust / n_rx_members:.1f}%)")

for order, label in (("desc", "MOST sustained"), ("asc", "LEAST sustained")):
    rows = con.execute(f"""
        select drug_class, count(*) as members,
            round(100.0 * avg(case when n_fills >= 3 and span >= 90 then 1 else 0 end), 1) as s
        from (select member_id, drug_class, count(*) as n_fills,
                     date_diff('day', min(fd), max(fd)) as span
              from rx group by 1, 2)
        group by 1 having count(*) >= 2000 order by s {order} limit 7""").fetchall()
    print(f"\n{label} classes (>=2,000 members): class | members | % sustained")
    for r in rows:
        print(f"  {r[0][:52]:<52} {r[1]:>7,} {r[2]:>6}")

gaps = con.execute("""
select gap, count(*) as n from (
  select date_diff('day', lag(fd) over (partition by member_id, drug_class order by fd), fd)
      as gap from rx) where gap is not null group by 1 order by 1
""").df()
total_gaps = gaps["n"].sum()
gap0 = int(gaps.loc[gaps["gap"] == 0, "n"].sum())
in_refill_band = int(gaps.loc[gaps["gap"].between(25, 35), "n"].sum())
med_gap = con.execute("""
select median(gap) from (
  select date_diff('day', lag(fd) over (partition by member_id, drug_class order by fd), fd)
      as gap from rx) where gap > 0""").fetchone()[0]
print(
    f"\nconsecutive same-class fill gaps: {total_gaps:,} | same-day {100 * gap0 / total_gaps:.1f}% "
    f"| in 25-35d band {100 * in_refill_band / total_gaps:.1f}% | median (gap>0): {med_gap:.0f}d"
)

print("\n=== D. code concentration (for the figures) ===")
freq = {}
freq["diagnosis codes"] = (
    con.execute("select dn, count(*) as n from cl group by 1 order by n desc").df()["n"].to_numpy()
)
freq["NDCs"] = (
    con.execute("select ndc, count(*) as n from rx group by 1 order by n desc").df()["n"].to_numpy()
)
freq["drug classes"] = (
    con.execute("select drug_class, count(*) as n from rx group by 1 order by n desc")
    .df()["n"]
    .to_numpy()
)
for name, arr in freq.items():
    tot = arr.sum()
    cov = {k: 100 * arr[:k].sum() / tot for k in (10, 100, 1000) if k <= len(arr)}
    print(
        f"{name}: {len(arr):,} distinct; coverage "
        + " ".join(f"top{k}={v:.0f}%" for k, v in cov.items())
    )

colors = {"diagnosis codes": BLUE, "NDCs": ORANGE, "drug classes": AQUA}

fig, ax = plt.subplots(figsize=(7.8, 4.6), layout="constrained")
for name, arr in freq.items():
    ax.plot(np.arange(1, len(arr) + 1), arr, color=colors[name], lw=2, label=name)
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_title("Every code vocabulary is heavy-headed with a long, thin tail", loc="left")
ax.set_xlabel("code rank (log)")
ax.set_ylabel("occurrences in window (log)")
leg = ax.legend(frameon=True, framealpha=1.0)
leg.get_frame().set_facecolor(SURFACE)
leg.get_frame().set_edgecolor(GRID)
sns.despine(left=True, bottom=True)
fig.savefig(OUT / "2026-11-02_eda-session_rx_fig01_rank_frequency.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.8, 4.6), layout="constrained")
for name, arr in freq.items():
    cum = 100 * np.cumsum(arr) / arr.sum()
    ax.plot(np.arange(1, len(arr) + 1), cum, color=colors[name], lw=2, label=name)
ax.set_xscale("log")
ax.set_title(
    "Drug classes saturate fast (top 100 = 87% of fills);\n"
    "raw diagnosis codes and NDCs need thousands",
    loc="left",
)
ax.set_xlabel("top k codes (log)")
ax.set_ylabel("cumulative % of rows/fills")
ax.set_ylim(0, 102)
leg = ax.legend(loc="lower right", frameon=True, framealpha=1.0)
leg.get_frame().set_facecolor(SURFACE)
leg.get_frame().set_edgecolor(GRID)
sns.despine(left=True, bottom=True)
fig.savefig(OUT / "2026-11-02_eda-session_rx_fig02_cumulative_coverage.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.8, 4.2), layout="constrained")
capped = per_m["fills"].clip(upper=50)
dist = 100 * capped.value_counts().sort_index() / n_rx_members
ax.bar(dist.index, dist.to_numpy(), color=BLUE, width=0.85, edgecolor=SURFACE, linewidth=0.6)
ax.set_title("Fills per member: long right tail past a mode of 1–2", loc="left")
ax.set_xlabel(f"fills per member in window, capped at 50+ (n = {n_rx_members:,} members)")
ax.set_ylabel("% of rx members")
sns.despine(left=True, bottom=True)
fig.savefig(OUT / "2026-11-02_eda-session_rx_fig03_fills_per_member.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.8, 4.2), layout="constrained")
g = gaps[(gaps["gap"] >= 1) & (gaps["gap"] <= 120)]
ax.bar(g["gap"], 100 * g["n"] / total_gaps, color=BLUE, width=1.0)
ax.set_title("Refill cycles are real: same-class fill gaps spike at ~30 days", loc="left")
ax.set_xlabel(
    f"days between consecutive fills of the same drug class (n = {total_gaps:,} gaps; shown 1–120)"
)
ax.set_ylabel("% of gaps")
sns.despine(left=True, bottom=True)
fig.savefig(OUT / "2026-11-02_eda-session_rx_fig04_interfill_gaps.png")
plt.close(fig)

print("\nfigures written to", OUT)
