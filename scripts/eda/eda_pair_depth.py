"""Depth of member x drug-class and member x L2-condition pairs, two views.

1. pooled quartile bins (ties merge; comparative view against the whole pair population)
2. per-group quantiles (each class/condition against its OWN distribution - the view
   Lauren asked for on 2026-11-02)
Binning for the final characterization is an open decision (principled low/med/high,
next session); this script documents both views tried.
"""

import numpy as np

from oscar_cs.db import connect_views
from oscar_cs.health_status import (
    ANALYSIS_WINDOW_END,
    ANALYSIS_WINDOW_START,
    NON_CONDITION_CHAPTERS,
)

con = connect_views()
W = {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END}
excl = ", ".join(f"'{c}'" for c in NON_CONDITION_CHAPTERS)

RX_PAIRS = """
select drug_class as grp, member_id, count(*) as n from prescription_drugs
where try_cast(date_svc as date) between $ws and $we group by 1, 2"""
DX_PAIRS = f"""
select regexp_replace(ccs.ccs_2_desc, '\\s*\\[[^\\]]*\\]\\s*$', '') as grp,
       cl.member_id, count(*) as n
from claim_lines cl
join ccs on upper(trim(replace(cl.diag1, '.', ''))) = ccs.diag
where try_cast(cl.date_svc as date) between $ws and $we
  and ccs.ccs_1_desc not in ({excl})
group by 1, 2"""


def pooled_bins(pairs_sql, title, unit):
    pairs = con.execute(pairs_sql, W).df()
    qs = pairs["n"].quantile([0.25, 0.5, 0.75])
    cuts = np.unique(qs.to_numpy())
    pairs["b"] = np.searchsorted(cuts, pairs["n"].to_numpy(), side="left")
    print(f"\n### {title} - POOLED quartile bins (p25/p50/p75 = {qs.tolist()}; ties merge)")
    marg = (100 * pairs["b"].value_counts(normalize=True).sort_index()).round(1)
    print(f"all {len(pairs):,} pairs:", marg.to_dict())
    top = pairs.groupby("grp")["member_id"].size().nlargest(15).index
    tbl = pairs[pairs["grp"].isin(top)].pivot_table(
        index="grp", columns="b", values="n", aggfunc="size", fill_value=0
    )
    pct = (100 * tbl.div(tbl.sum(axis=1), axis=0)).round(1)
    pct["members"] = tbl.sum(axis=1)
    print(pct.sort_values(pct.columns[-2], ascending=False).to_string())


def per_group_quantiles(pairs_sql, title, unit):
    rows = con.execute(
        f"""
        with pairs as ({pairs_sql}),
        top as (select grp from pairs group by grp order by count(*) desc limit 15)
        select grp, count(*) as members,
            quantile_disc(n, 0.25), quantile_disc(n, 0.50), quantile_disc(n, 0.75),
            quantile_disc(n, 0.90), quantile_disc(n, 0.99), max(n)
        from pairs where grp in (select grp from top)
        group by grp order by 5 desc, 6 desc, members desc""",
        W,
    ).fetchall()
    print(f"\n### {title} - PER-GROUP quantiles ({unit}/member: p25 p50 p75 p90 p99 max)")
    for r in rows:
        print(f"  {r[0][:46]:<46} {r[1]:>7,} | " + " ".join(f"{v:.0f}" for v in r[2:]))


pooled_bins(RX_PAIRS, "RX fills per member x class pair", "fills")
pooled_bins(DX_PAIRS, "DX lines per member x condition pair", "lines")
per_group_quantiles(RX_PAIRS, "RX classes", "fills")
per_group_quantiles(DX_PAIRS, "DX conditions", "lines")
