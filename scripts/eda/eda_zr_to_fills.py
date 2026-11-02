"""Do prescription fills follow Z-code (checkup/screening) or R-code (symptom) claim days?

Unit: member x claim-day, classified by what the day carries:
  diagnosis day  = any mapped non-Z/non-R code that day (whatever else is present)
  R-only day     = R code(s), no mapped diagnosis (Z may also be present)
  Z-only day     = Z code(s) only
  junk-only day  = only unmapped codes
Restricted to members who appear in prescription_drugs at all, and to claim days
2015-01-01 .. 2018-05-05 so a 30-day follow-up window always fits inside rx coverage
(rx ends 2018-06-04) - avoids right-censoring bias between classes.
"""

from oscar_cs.db import connect_views
from oscar_cs.health_status import RESIDUAL_CHAPTER, SYMPTOMS_CHAPTER

con = connect_views()
norm = "upper(trim(replace(diag1, '.', '')))"

con.execute(f"""
create temp table visit_days as
with cl as (
    select member_id, try_cast(date_svc as date) as d, {norm} as dn
    from claim_lines
    where try_cast(date_svc as date) between date '2015-01-01' and date '2018-05-05'
),
flagged as (
    select cl.member_id, cl.d,
        max(case when cl.dn like 'Z%' then 1 else 0 end) as has_z,
        max(case when cl.dn like 'R%' then 1 else 0 end) as has_r,
        max(case when cl.dn not like 'Z%' and cl.dn not like 'R%'
                  and ccs.diag is not null then 1 else 0 end) as has_dx
    from cl left join ccs on cl.dn = ccs.diag
    group by 1, 2
)
select member_id, d,
    case when has_dx = 1 then '1 diagnosis day'
         when has_r = 1 then '2 R-only day'
         when has_z = 1 then '3 Z-only day'
         else '4 junk-only day' end as cls
from flagged
where member_id in (select distinct member_id from prescription_drugs)
""")

con.execute("""
create temp table fills as
select member_id, try_cast(date_svc as date) as fd, drug_category
from prescription_drugs
where try_cast(date_svc as date) is not null
""")

con.execute("""
create temp table first_fill as
select v.member_id, v.d, min(f.fd) as ffd
from visit_days v
join fills f on v.member_id = f.member_id and f.fd >= v.d and f.fd <= v.d + 30
group by 1, 2
""")

print("### follow-up fill rates by claim-day class (members present in rx; days <= 2018-05-05)")
rows = con.execute("""
select v.cls,
    count(*) as n_days,
    count(distinct v.member_id) as n_members,
    round(100.0 * avg(case when ff.ffd = v.d then 1 else 0 end), 1) as same_day,
    round(100.0 * avg(case when ff.ffd <= v.d + 7 then 1 else 0 end), 1) as within_7d,
    round(100.0 * avg(case when ff.ffd is not null then 1 else 0 end), 1) as within_30d,
    median(case when ff.ffd is not null then ff.ffd - v.d end) as median_gap_days
from visit_days v left join first_fill ff on v.member_id = ff.member_id and v.d = ff.d
group by 1 order by 1
""").fetchall()
print("class | claim-days | members | %same-day | %<=7d | %<=30d | median gap")
for r in rows:
    print(" | ".join(str(x) for x in r))

print("\n### top drug categories filled within 7 days after R-only vs Z-only days")
for cls, label in [
    ("2 R-only day", "after R-only (symptom) days"),
    ("3 Z-only day", "after Z-only (checkup) days"),
    ("1 diagnosis day", "after diagnosis days (baseline)"),
]:
    rows = con.execute(f"""
        select f.drug_category, count(distinct v.member_id || '|' || v.d) as visit_days
        from visit_days v
        join fills f on v.member_id = f.member_id and f.fd >= v.d and f.fd <= v.d + 7
        where v.cls = '{cls}'
        group by 1 order by 2 desc limit 6
    """).fetchall()
    print(f"\n{label}:")
    for cat, n in rows:
        print(f"  {cat[:58]:<58} {n:>8,}")

print("\n### the claims-blind-spot check: symptom/admin-only members vs rx")
rows = con.execute(f"""
with per_m as (
    select cl.member_id,
        max(case when ccs.ccs_1_desc is not null
                  and ccs.ccs_1_desc not in ('{SYMPTOMS_CHAPTER}', '{RESIDUAL_CHAPTER}')
             then 1 else 0 end) as has_cond,
        max(case when ccs.ccs_1_desc in ('{SYMPTOMS_CHAPTER}', '{RESIDUAL_CHAPTER}')
             then 1 else 0 end) as has_sympres
    from claim_lines cl
    left join ccs on {norm} = ccs.diag
    where try_cast(cl.date_svc as date) >= date '2015-01-01'
    group by 1
),
sa as (select member_id from per_m where has_cond = 0 and has_sympres = 1),
rxc as (select member_id, count(*) as n_fills from fills group by 1)
select
    (select count(*) from sa) as symptom_admin_only_members,
    count(rxc.member_id) as of_which_in_rx,
    round(100.0 * count(rxc.member_id) / (select count(*) from sa), 1) as pct_in_rx,
    median(rxc.n_fills) as median_fills_those,
    round(100.0 * avg(case when rxc.n_fills >= 5 then 1 else 0 end), 1) as pct_5plus_fills
from sa left join rxc using (member_id)
""").fetchall()
print("sympt/admin-only members | in rx | % | median fills | % with 5+ fills")
print(" | ".join(str(x) for x in rows[0]))

print("\n(comparator) members WITH >=1 condition diagnosis: rx presence + fills")
rows = con.execute(f"""
with per_m as (
    select cl.member_id,
        max(case when ccs.ccs_1_desc is not null
                  and ccs.ccs_1_desc not in ('{SYMPTOMS_CHAPTER}', '{RESIDUAL_CHAPTER}')
             then 1 else 0 end) as has_cond
    from claim_lines cl
    left join ccs on {norm} = ccs.diag
    where try_cast(cl.date_svc as date) >= date '2015-01-01'
    group by 1
),
cd as (select member_id from per_m where has_cond = 1),
rxc as (select member_id, count(*) as n_fills from fills group by 1)
select (select count(*) from cd) as members,
    round(100.0 * count(rxc.member_id) / (select count(*) from cd), 1) as pct_in_rx,
    median(rxc.n_fills) as median_fills
from cd left join rxc using (member_id)
""").fetchall()
print("members | % in rx | median fills:", rows[0])
