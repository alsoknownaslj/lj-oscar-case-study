"""Repetition structure of conditions: does the data want a binary or ternary taxonomy?

Unit: (member, CCS level-2 condition) pair, condition chapters only, canonical window.
Shape classes (runway-restricted: first date >=365d before window end, so long spans CAN
be observed):
  single     1 distinct date
  arc        >=2 dates, total span <= 180d (bounded burst, incl. tight clusters)
  recurrent  span > 180d but with a quiet gap > 180d (goes away, comes back)
  continuous span > 180d, no gap > 180d (ongoing contact)
Outputs: per-category signature table + stacked-bar figure, span-CDF exemplars figure,
decomposition of the CURRENT chronic rule (>=2 dates >=30d apart) into the new classes.
"""

import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

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
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
GRAY = "#c3c2b7"

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
con.execute(
    f"""
create temp table cond_dates as
select distinct cl.member_id,
    regexp_replace(ccs.ccs_2_desc, '\\s*\\[[^\\]]*\\]\\s*$', '') as cat,
    try_cast(cl.date_svc as date) as d
from claim_lines cl
join ccs on upper(trim(replace(cl.diag1, '.', ''))) = ccs.diag
where try_cast(cl.date_svc as date) between $ws and $we
  and ccs.ccs_1_desc not in ({excl})
""",
    {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END},
)

con.execute("""
create temp table pairs as
with gaps as (
    select member_id, cat, d,
        date_diff('day', lag(d) over (partition by member_id, cat order by d), d) as g
    from cond_dates
)
select member_id, cat,
    count(*) as n_dates,
    date_diff('day', min(d), max(d)) as span,
    coalesce(max(g), 0) as max_gap,
    median(g) as med_gap,
    min(d) as first_d,
    date_diff('day', max(d), date '2018-06-04') as tail_days
from gaps group by 1, 2
""")

pairs = con.execute("""
select *,
    first_d <= date '2017-06-04' as runway,
    case when n_dates = 1 then 'single'
         when span <= 180 then 'arc'
         when max_gap > 180 then 'recurrent'
         else 'continuous' end as shape,
    (n_dates >= 2 and span >= 30) as cur_chronic
from pairs
""").df()

run = pairs[pairs["runway"]]
print(f"pairs total: {len(pairs):,} | with >=365d runway: {len(run):,}")
shape_mix = (100 * run["shape"].value_counts(normalize=True)).round(1)
print("overall shape mix (runway pairs):", shape_mix.to_dict())
print("\nmedian quiet tail (days from last date to window end) by shape:")
print(run.groupby("shape")["tail_days"].median().round(0).to_dict())

print("\n--- decomposition of the CURRENT chronic flag (runway pairs) ---")
cur = run[run["cur_chronic"]]
decomp = (100 * cur["shape"].value_counts(normalize=True)).round(1)
print(f"current-chronic pairs: {len(cur):,} -> {decomp.to_dict()}")
print("(arc here = would downgrade to 'episode' under a ternary rule)")

SHAPES = ["continuous", "recurrent", "arc", "single"]
cat_stats = (
    run.assign(one=1)
    .pivot_table(index="cat", columns="shape", values="one", aggfunc="sum", fill_value=0)
    .reindex(columns=SHAPES, fill_value=0)
)
cat_stats["pairs"] = cat_stats.sum(axis=1)
for s in SHAPES:
    cat_stats[f"pct_{s}"] = 100 * cat_stats[s] / cat_stats["pairs"]
med = run.groupby("cat").agg(med_span=("span", "median"), med_gap=("med_gap", "median"))
cat_stats = cat_stats.join(med)
eligible = cat_stats[cat_stats["pairs"] >= 3000].copy()
print(f"\ncategories with >=3,000 runway pairs: {len(eligible)}")

extra = [
    c
    for c in (
        "Respiratory infections",
        "Sprains and strains",
        "Asthma",
        "Chronic obstructive pulmonary disease and bronchiectasis",
        "Anxiety disorders",
    )
    if c in eligible.index
]
show = (
    pd.concat(
        [
            eligible.nlargest(6, "pct_continuous"),
            eligible.nlargest(6, "pct_arc"),
            eligible.loc[extra],
        ]
    )
    .drop_duplicates()
    .sort_values("pct_continuous", ascending=False)
)
cols = ["pairs", "pct_single", "pct_arc", "pct_recurrent", "pct_continuous", "med_span", "med_gap"]
print("\ncategory | " + " | ".join(cols))
for cat, r in show[cols].iterrows():
    print(
        f"{cat[:42]:<42} | "
        + " | ".join(
            f"{v:,.0f}" if c == "pairs" else f"{v:.1f}" for c, v in zip(cols, r, strict=True)
        )
    )

# --- fig 1: shape signatures, stacked bars ---------------------------------------
rows = show.iloc[::-1]
labels = ["\n".join(textwrap.wrap(c, 30)) for c in rows.index]
fig, ax = plt.subplots(figsize=(8.4, 6.8), layout="constrained")
left = np.zeros(len(rows))
for shape, color, lbl in [
    ("continuous", BLUE, "continuous (span>180d, no 180d gap)"),
    ("recurrent", ORANGE, "recurrent (quiet >180d, returns)"),
    ("arc", AQUA, "bounded arc (≥2 dates, span ≤180d)"),
    ("single", GRAY, "single date"),
]:
    vals = rows[f"pct_{shape}"].to_numpy()
    ax.barh(
        labels,
        vals,
        left=left,
        color=color,
        height=0.72,
        edgecolor=SURFACE,
        linewidth=1.0,
        label=lbl,
    )
    left += vals
ax.set_xlim(0, 100)
ax.set_title(
    "Condition 'shapes' separate cleanly: management vs episodes\n"
    "(member×condition pairs with ≥365d runway)",
    loc="left",
)
ax.set_xlabel("% of the category's member×condition pairs")
ax.tick_params(axis="y", labelcolor=INK_2)
leg = ax.legend(loc="lower right", fontsize=9, frameon=True, framealpha=1.0)
leg.get_frame().set_facecolor(SURFACE)
leg.get_frame().set_edgecolor(GRID)
sns.despine(left=True, bottom=True)
fig.savefig(OUT / "2026-11-02_eda-session_repetition_fig1_shapes.png")
plt.close(fig)

# --- fig 2: span CDF for exemplars -----------------------------------------------
exemplars = list(
    dict.fromkeys(
        list(eligible.nlargest(2, "pct_continuous").index)
        + list(eligible.nlargest(2, "pct_arc").index)
        + (["Respiratory infections"] if "Respiratory infections" in eligible.index else [])
    )
)[:5]
slot_colors = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA]
fig, ax = plt.subplots(figsize=(8.0, 4.8), layout="constrained")
repeat = run[run["n_dates"] >= 2]
for cat, color in zip(exemplars, slot_colors, strict=False):
    spans = np.sort(repeat.loc[repeat["cat"] == cat, "span"].to_numpy())
    y = 100 * np.arange(1, len(spans) + 1) / len(spans)
    ax.plot(spans, y, color=color, lw=2.2, label=f"{cat[:34]} ({len(spans):,})")
ax.axvline(180, color=AXIS, lw=1, ls=":")
ax.annotate("180d", xy=(180, 4), color=MUTED, xytext=(190, 4))
ax.set_xlim(0, 1000)
ax.set_ylim(0, 102)
ax.set_title("Episodic conditions saturate by ~6 months; chronic ones keep going", loc="left")
ax.set_xlabel("total span of the pair's claim dates, days (repeat pairs, ≥365d runway)")
ax.set_ylabel("cumulative % of repeat pairs")
leg = ax.legend(loc="lower right", fontsize=9, frameon=True, framealpha=1.0)
leg.get_frame().set_facecolor(SURFACE)
leg.get_frame().set_edgecolor(GRID)
sns.despine(left=True, bottom=True)
fig.savefig(OUT / "2026-11-02_eda-session_repetition_fig2_span_cdf.png")
plt.close(fig)
print("\nexemplars for CDF:", exemplars)
print("figures written")
