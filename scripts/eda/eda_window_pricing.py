"""Price the canonical analysis window [2015-09-01, 2018-06-04] for both tables.

Reproduces the numbers behind the 2026-11-02 window decision (memory/decisions.md):
rows/members dropped per table, in-window population split, and the taper evidence
(monthly volumes near both edges).
"""

from oscar_cs.db import connect_views
from oscar_cs.health_status import ANALYSIS_WINDOW_END, ANALYSIS_WINDOW_START

con = connect_views()
W = {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END}

for table in ("claim_lines", "prescription_drugs"):
    total, nulls, pre, post, kept, m_kept, m_all = con.execute(
        f"""
        select count(*),
            sum(case when try_cast(date_svc as date) is null then 1 else 0 end),
            sum(case when try_cast(date_svc as date) < $ws then 1 else 0 end),
            sum(case when try_cast(date_svc as date) > $we then 1 else 0 end),
            sum(case when try_cast(date_svc as date) between $ws and $we
                then 1 else 0 end),
            count(distinct case when try_cast(date_svc as date) between $ws and $we
                then member_id end),
            count(distinct member_id)
        from {table}""",
        W,
    ).fetchone()
    print(
        f"{table}: total {total:,} | null {nulls} | pre {pre:,} | post {post:,} "
        f"| kept {kept:,} ({100 * kept / total:.1f}%) "
        f"| members {m_kept:,} of {m_all:,}"
    )

both, c_only, r_only, union = con.execute(
    """
    with c as (select distinct member_id from claim_lines
               where try_cast(date_svc as date) between $ws and $we),
         r as (select distinct member_id from prescription_drugs
               where try_cast(date_svc as date) between $ws and $we)
    select (select count(*) from c join r using (member_id)),
        (select count(*) from c where member_id not in (select member_id from r)),
        (select count(*) from r where member_id not in (select member_id from c)),
        (select count(*) from (select member_id from c union select member_id from r))
    """,
    W,
).fetchone()
print(
    f"in-window populations: union {union:,} = both {both:,} "
    f"+ claims-only {c_only:,} + rx-only {r_only:,}"
)

print("\nmonthly volumes near the edges (the taper evidence):")
for table in ("claim_lines", "prescription_drugs"):
    rows = con.execute(f"""
        select date_trunc('month', try_cast(date_svc as date)) as m, count(*)
        from {table}
        where try_cast(date_svc as date) >= date '2018-01-01'
        group by 1 order by 1""").fetchall()
    print(f"  {table} 2018:", {str(m)[:7]: n for m, n in rows})
