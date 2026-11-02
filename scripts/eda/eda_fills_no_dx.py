"""Which drug fills have no preceding diagnosis claim?

Two separate answers:
  structural - fills by rx-only members (never in claim_lines at all)
  temporal   - fills by both-table members with no claim in the 30/90/365 days before

Left-censoring: claims effectively start 2015-09, so the temporal analysis uses fills
dated 2016-09-01..2018-06-04, where a full 365-day lookback sits inside claims coverage.
'Preceding claim' = any claim day (incl. Z/R); a stricter condition-claim variant is
reported at the headline level.
"""

from oscar_cs.db import connect_views
from oscar_cs.health_status import NON_CONDITION_CHAPTERS

con = connect_views()
norm = "upper(trim(replace(diag1, '.', '')))"
excl = ", ".join(f"'{c}'" for c in NON_CONDITION_CHAPTERS)

con.execute("""
create temp table fills as
select member_id, try_cast(date_svc as date) as fd, drug_category
from prescription_drugs
where try_cast(date_svc as date) is not null
""")
con.execute(f"""
create temp table claim_days as
select cl.member_id, try_cast(cl.date_svc as date) as d,
    max(case when ccs.ccs_1_desc is not null and ccs.ccs_1_desc not in ({excl})
        then 1 else 0 end) as is_cond
from claim_lines cl
left join ccs on {norm} = ccs.diag
where try_cast(cl.date_svc as date) >= date '2015-01-01'
group by 1, 2
""")

(n_fills_all, n_pre_cov) = con.execute("""
select count(*), sum(case when fd < date '2015-09-01' then 1 else 0 end) from fills
""").fetchone()
print(
    f"all fills: {n_fills_all:,}; before claims coverage (2015-09): {n_pre_cov:,} "
    f"({100 * n_pre_cov / n_fills_all:.1f}%) - blind zone, excluded from temporal analysis"
)

(rxonly_members, rxonly_fills) = con.execute("""
select count(distinct member_id), count(*) from fills
where member_id not in (select distinct member_id from claim_days)
""").fetchone()
print(
    f"STRUCTURAL: rx-only members: {rxonly_members:,}, their fills: {rxonly_fills:,} "
    f"({100 * rxonly_fills / n_fills_all:.1f}% of all fills) - no claim can ever precede"
)

con.execute("""
create temp table scored as
select f.member_id, f.fd, f.drug_category, c.d as last_claim, f.fd - c.d as gap
from (select * from fills
      where fd >= date '2016-09-01'
        and member_id in (select distinct member_id from claim_days)) f
asof left join claim_days c
    on f.member_id = c.member_id and c.d <= f.fd
""")
con.execute("""
create temp table scored_cond as
select f.member_id, f.fd, cc.d as last_cond_claim
from (select * from fills
      where fd >= date '2016-09-01'
        and member_id in (select distinct member_id from claim_days)) f
asof left join (select member_id, d from claim_days where is_cond = 1) cc
    on f.member_id = cc.member_id and cc.d <= f.fd
""")

row = con.execute("""
select count(*),
    round(100.0 * avg(case when last_claim is null or gap > 365 then 1 else 0 end), 1),
    round(100.0 * avg(case when last_claim is null or gap > 90 then 1 else 0 end), 1),
    round(100.0 * avg(case when last_claim is null or gap > 30 then 1 else 0 end), 1),
    median(gap)
from scored
""").fetchone()
print(f"\nTEMPORAL (both-table members, fills 2016-09+): {row[0]:,} fills")
print(
    f"  no claim in prior 365d: {row[1]}% | prior 90d: {row[2]}% | prior 30d: {row[3]}% "
    f"| median gap to last claim: {row[4]} days"
)
row = con.execute("""
select round(100.0 * avg(case when last_cond_claim is null
    or fd - last_cond_claim > 365 then 1 else 0 end), 1) from scored_cond
""").fetchone()
print(f"  stricter variant - no CONDITION claim in prior 365d: {row[0]}%")

print("\n### categories MOST often unpreceded (no claim in prior 365d; >=5,000 fills)")
rows = con.execute("""
select drug_category, count(*) as n_fills,
    round(100.0 * avg(case when last_claim is null or gap > 365 then 1 else 0 end), 1) as no365,
    round(100.0 * avg(case when last_claim is null or gap > 90 then 1 else 0 end), 1) as no90,
    median(gap) as med_gap
from scored group by 1 having count(*) >= 5000 order by no365 desc limit 12
""").fetchall()
print("category | fills | %no-claim 365d | %no 90d | median gap")
for r in rows:
    print(f"{r[0][:46]} | {r[1]:,} | {r[2]} | {r[3]} | {r[4]}")

print("\n### categories LEAST often unpreceded (same threshold)")
rows = con.execute("""
select drug_category, count(*) as n_fills,
    round(100.0 * avg(case when last_claim is null or gap > 365 then 1 else 0 end), 1) as no365,
    round(100.0 * avg(case when last_claim is null or gap > 90 then 1 else 0 end), 1) as no90,
    median(gap) as med_gap
from scored group by 1 having count(*) >= 5000 order by no365 asc limit 6
""").fetchall()
print("category | fills | %no-claim 365d | %no 90d | median gap")
for r in rows:
    print(f"{r[0][:46]} | {r[1]:,} | {r[2]} | {r[3]} | {r[4]}")

print("\n### what rx-only members take (top 10 categories of their fills)")
rows = con.execute("""
select drug_category, count(*) as n, count(distinct member_id) as members
from fills
where member_id not in (select distinct member_id from claim_days)
group by 1 order by n desc limit 10
""").fetchall()
tot = rxonly_fills
print("category | fills | % of rx-only fills | members")
for r in rows:
    print(f"{r[0][:46]} | {r[1]:,} | {100 * r[1] / tot:.1f} | {r[2]:,}")

print("\n### composition of the unpreceded pool (both-members, no claim prior 365d)")
rows = con.execute("""
select drug_category, count(*) as n
from scored where last_claim is null or gap > 365
group by 1 order by n desc limit 8
""").fetchall()
(pool,) = con.execute(
    "select count(*) from scored where last_claim is null or gap > 365"
).fetchone()
for r in rows:
    print(f"{r[0][:46]} | {r[1]:,} | {100 * r[1] / pool:.1f}% of pool")
print(f"(pool: {pool:,} fills)")
