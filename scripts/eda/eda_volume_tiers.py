"""Member utilization volume tiers (median split) and metric-pairing correlations.

Reproduces the 2026-11-02 numbers: median claim lines / fills per member, the
none/low/mid/high contingency over the in-window union, and Spearman rho for all four
volume/distinct metric pairings (Lauren's confound check).
Median and quartile tier cuts were both REJECTED on 2026-11-02 in favor of principled
low/med/high bins, to be designed next session - this script documents what was tried.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from oscar_cs.db import connect_views
from oscar_cs.health_status import (
    ANALYSIS_WINDOW_END,
    ANALYSIS_WINDOW_START,
    NON_CONDITION_CHAPTERS,
)

con = connect_views()
W = {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END}
excl = ", ".join(f"'{c}'" for c in NON_CONDITION_CHAPTERS)

dx = con.execute(
    """
    select member_id, count(*) as dx_vol from claim_lines
    where try_cast(date_svc as date) between $ws and $we group by 1""",
    W,
).df()
rx = con.execute(
    """
    select member_id, count(*) as rx_vol from prescription_drugs
    where try_cast(date_svc as date) between $ws and $we group by 1""",
    W,
).df()
dxc = con.execute(
    f"""
    select cl.member_id, count(distinct ccs.ccs_2_desc) as dx_distinct
    from claim_lines cl
    join ccs on upper(trim(replace(cl.diag1, '.', ''))) = ccs.diag
    where try_cast(cl.date_svc as date) between $ws and $we
      and ccs.ccs_1_desc not in ({excl}) group by 1""",
    W,
).df()
rxc = con.execute(
    """
    select member_id, count(distinct drug_class) as rx_distinct from prescription_drugs
    where try_cast(date_svc as date) between $ws and $we group by 1""",
    W,
).df()

med_dx, med_rx = dx["dx_vol"].median(), rx["rx_vol"].median()
print(f"median dx lines/member = {med_dx:.0f}; median rx fills/member = {med_rx:.0f}")


def tier(s, med):
    return np.select([s < med, s == med], ["low", "mid"], default="high")


dx["t"] = tier(dx["dx_vol"], med_dx)
rx["t"] = tier(rx["rx_vol"], med_rx)
univ = dx[["member_id", "t"]].merge(
    rx[["member_id", "t"]], on="member_id", how="outer", suffixes=("_dx", "_rx")
)
univ = univ.fillna({"t_dx": "none", "t_rx": "none"})
order = ["none", "low", "mid", "high"]
ct = pd.crosstab(univ["t_dx"], univ["t_rx"]).reindex(index=order, columns=order)
print(f"\ncontingency, median volume tiers (union {len(univ):,}):")
print(ct.to_string())
print("\n% of union:")
print((100 * ct / len(univ)).round(1).to_string())

both = (
    dx.merge(rx, on="member_id")
    .merge(dxc, on="member_id", how="left")
    .fillna({"dx_distinct": 0})
    .merge(rxc, on="member_id")
)
print(f"\nSpearman rho, both-table members (n={len(both):,}):")
for a, b in [
    ("dx_vol", "rx_vol"),
    ("dx_distinct", "rx_distinct"),
    ("dx_distinct", "rx_vol"),
    ("dx_vol", "rx_distinct"),
]:
    rho, _ = spearmanr(both[a], both[b])
    print(f"  {a} vs {b}: {rho:.3f}")
