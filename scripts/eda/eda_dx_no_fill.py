"""Which diagnoses are NOT followed by any prescription fill?

Unit: member x claim-day x CCS level-2 condition category (condition chapters only;
Z/R/Residual covered separately). Restricted to members present in rx and claim days
2015-01-01..2018-05-05 (full 30-day follow-up inside rx coverage). A day with several
categories credits each. Two views per category:
  - day view:    % of its claim-days with NO fill within 7 / 30 days
  - member view: % of its members never filling within 30d of ANY of their days with it
"""

from oscar_cs.db import connect_views
from oscar_cs.health_status import NON_CONDITION_CHAPTERS

con = connect_views()
norm = "upper(trim(replace(diag1, '.', '')))"
excl = ", ".join(f"'{c}'" for c in NON_CONDITION_CHAPTERS)

con.execute(f"""
create temp table cat_days as
select distinct
    cl.member_id,
    try_cast(cl.date_svc as date) as d,
    ccs.ccs_1_desc as chapter,
    regexp_replace(ccs.ccs_2_desc, '\\s*\\[[^\\]]*\\]\\s*$', '') as cat
from claim_lines cl
join ccs on {norm} = ccs.diag
where try_cast(cl.date_svc as date) between date '2015-01-01' and date '2018-05-05'
  and ccs.ccs_1_desc not in ({excl})
  and cl.member_id in (select distinct member_id from prescription_drugs)
""")

con.execute("""
create temp table day_fill as
with days as (select distinct member_id, d from cat_days)
select days.member_id, days.d, min(f.fd) as ffd
from days
join (select member_id, try_cast(date_svc as date) as fd
      from prescription_drugs where try_cast(date_svc as date) is not null) f
  on days.member_id = f.member_id and f.fd >= days.d and f.fd <= days.d + 30
group by 1, 2
""")

con.execute("""
create temp table scored as
select c.chapter, c.cat, c.member_id, c.d,
    case when df.ffd is null then 1 else 0 end as no30,
    case when df.ffd is null or df.ffd > c.d + 7 then 1 else 0 end as no7
from cat_days c
left join day_fill df on c.member_id = df.member_id and c.d = df.d
""")

summary = con.execute("""
with per_cat_member as (
    select chapter, cat, member_id, min(no30) as never30  -- 1 only if ALL their days unfilled
    from scored group by 1, 2, 3
),
member_view as (
    select chapter, cat, count(*) as n_members,
        round(100.0 * avg(never30), 1) as pct_members_never30
    from per_cat_member group by 1, 2
),
day_view as (
    select chapter, cat, count(*) as n_days,
        round(100.0 * avg(no7), 1) as pct_days_nofill7,
        round(100.0 * avg(no30), 1) as pct_days_nofill30
    from scored group by 1, 2
)
select d.cat, d.chapter, d.n_days, m.n_members,
       d.pct_days_nofill7, d.pct_days_nofill30, m.pct_members_never30
from day_view d join member_view m using (chapter, cat)
where m.n_members >= 1000
order by d.pct_days_nofill30 desc
""").fetchall()

base = con.execute("""
select count(*), round(100.0 * avg(no7), 1), round(100.0 * avg(no30), 1) from scored
""").fetchone()
print(
    f"baseline, all condition-category days: {base[0]:,} days | "
    f"no fill <=7d: {base[1]}% | no fill <=30d: {base[2]}%"
)
print(f"categories with >=1,000 members: {len(summary)}")

hdr = "category | chapter | days | members | %days no fill<=7d | <=30d | %members never"
print("\n### LEAST likely to be followed by a fill (top 14)")
print(hdr)
for r in summary[:14]:
    print(f"{r[0][:44]} | {r[1][:28]} | {r[2]:,} | {r[3]:,} | {r[4]} | {r[5]} | {r[6]}")

print("\n### MOST likely to be followed by a fill (bottom 8)")
print(hdr)
for r in summary[-8:]:
    print(f"{r[0][:44]} | {r[1][:28]} | {r[2]:,} | {r[3]:,} | {r[4]} | {r[5]} | {r[6]}")
