"""EDA pass 1: id space, missingness/junk patterns, duplicates, CCS cardinality.

Interactive exploration for the 2026-11-02 session; promote anything load-bearing later.
Runs on the raw tables (parquet cache) with NO date filtering - neutral EDA.
"""

from oscar_cs.db import connect_views

con = connect_views()
norm = "upper(trim(replace(diag1, '.', '')))"


def q(sql):
    return con.execute(sql).fetchall()


def show(title, rows, cols):
    print(f"\n### {title}")
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(f"{v:,}" if isinstance(v, int) else str(v) for v in r))


print("=" * 30, "A. MEMBER ID SPACE", "=" * 30)
(n_union, lo, hi) = q("""
    select count(*), min(member_id), max(member_id) from (
      select distinct member_id from claim_lines
      union
      select distinct member_id from prescription_drugs)""")[0]
print(f"distinct members anywhere: {n_union:,}  (ids {lo} .. {hi})")
hi_num = int(hi[1:])
pct_unused = 100 * (hi_num - n_union) / hi_num
print(f"id space 1..{hi_num:,} -> {hi_num - n_union:,} numbers unused ({pct_unused:.1f}%)")

rows = q(f"""
  with c as (select distinct member_id from claim_lines),
       r as (select distinct member_id from prescription_drugs),
       u as (select member_id from c union select member_id from r),
       b as (select member_id,
                    (try_cast(substr(member_id, 2) as int) - 1) // {hi_num // 10 + 1} as dec
             from u)
  select b.dec,
         count(*) as n_ids,
         sum(case when c.member_id is not null and r.member_id is not null
             then 1 else 0 end) as n_both,
         sum(case when r.member_id is null then 1 else 0 end) as n_claims_only,
         sum(case when c.member_id is null then 1 else 0 end) as n_rx_only
  from b left join c on b.member_id = c.member_id
         left join r on b.member_id = r.member_id
  group by 1 order by 1""")
show(
    "ids per decile of the numeric id range (flat = random assignment)",
    rows,
    ["decile", "ids_used", "both", "claims_only", "rx_only"],
)

print()
print("=" * 30, "B. MISSINGNESS & JUNK", "=" * 30)
(n_null_date,) = q("select count(*) from claim_lines where try_cast(date_svc as date) is null")[0]
(n_empty_diag,) = q("select count(*) from claim_lines where trim(coalesce(diag1,'')) = ''")[0]
print(f"claims null/unparseable date_svc: {n_null_date:,} | empty diag1: {n_empty_diag:,}")
rows = q("""select year(try_cast(date_svc as date)) as y, count(*)
            from claim_lines where try_cast(date_svc as date) < date '2015-01-01'
            group by 1 order by 1""")
show("pre-2015 rows by year", rows, ["year", "rows"])

rows = q("""
  select cl.member_id, count(*) as null_rows, m.total_rows,
         string_agg(distinct cl.diag1, ' ') as diags
  from claim_lines cl
  join (select member_id, count(*) as total_rows from claim_lines group by 1) m using (member_id)
  where try_cast(cl.date_svc as date) is null
  group by 1, 3 order by 1""")
show(
    "the null-date rows: whose are they, and what codes do they carry",
    rows,
    ["member", "null_rows", "member_total_rows", "diag codes"],
)

print("\n-- unmapped codes (no CCS row), classified by shape --")
rows = q(f"""
  with u as (
    select {norm} as dn, count(*) as n_rows, count(distinct member_id) as n_members
    from claim_lines
    where {norm} not in (select diag from ccs)
    group by 1)
  select case
           when regexp_matches(dn, '^[0-9]+$') then 'digits only'
           when regexp_matches(dn, '^[A-Z]+$') then 'letters only'
           when regexp_matches(dn, '^[A-Z][0-9][0-9A-Z][0-9A-Z]{{0,4}}$') then 'valid ICD-10 shape'
           else 'other shape'
         end as shape,
         count(*) as n_codes, sum(n_rows) as n_rows, sum(n_members) as member_touches
  from u group by 1 order by n_rows desc""")
show("unmapped code shapes", rows, ["shape", "distinct_codes", "rows", "member_touches"])

rows = q(f"""
  select {norm} as dn, count(*) as n_rows, count(distinct member_id) as n_members,
         count(distinct date_svc) as n_dates
  from claim_lines where {norm} not in (select diag from ccs)
  group by 1 order by n_rows desc limit 8""")
show("top unmapped codes", rows, ["code", "rows", "members", "distinct_dates"])

rows = q(f"""
  with per_m as (
    select member_id,
           sum(case when {norm} not in (select diag from ccs) then 1 else 0 end) as junk,
           count(*) as total
    from claim_lines group by 1)
  select count(*) filter (junk > 0) as members_with_junk,
         max(junk) as max_junk_rows_one_member,
         count(*) filter (junk > 0 and junk = total) as members_all_junk
  from per_m""")[0]
print(
    f"\nmembers touched by >=1 unmapped row: {rows[0]:,}; "
    f"max unmapped rows for one member: {rows[1]}; "
    f"members with ONLY unmapped rows: {rows[2]}"
)

print()
print("=" * 30, "C. DUPLICATE CLAIM LINES", "=" * 30)
rows = q("""
  with g as (select member_id, date_svc, diag1, count(*) as cnt
             from claim_lines group by 1,2,3 having count(*) > 1)
  select count(*) as dup_groups, sum(cnt) as rows_involved,
         sum(cnt) - count(*) as excess_rows, max(cnt) as max_copies
  from g""")
dg, ri, ex, mx = rows[0] if rows[0][0] else (0, 0, 0, 0)
(total_rows,) = q("select count(*) from claim_lines")[0]
pct_excess = 100 * (ex or 0) / total_rows
print(
    f"exact (member, date, diag1) duplicate groups: {dg:,} | rows involved: {ri or 0:,} "
    f"| excess rows: {ex or 0:,} ({pct_excess:.3f}% of {total_rows:,}) | max copies: {mx}"
)
if dg:
    rows = q("""select cnt, count(*) from (select member_id, date_svc, diag1, count(*) as cnt
                from claim_lines group by 1,2,3 having count(*)>1) group by 1 order by 1""")
    show("multiplicity histogram", rows, ["copies", "groups"])
    rows = q("""select member_id, date_svc, diag1, count(*) as cnt from claim_lines
                group by 1,2,3 having count(*)>1 order by cnt desc, member_id limit 5""")
    show("sample duplicate groups", rows, ["member", "date", "diag1", "copies"])

print()
print("=" * 30, "D. Z-CODE / SYMPTOMS GROUNDING", "=" * 30)
for lvl2 in ("Factors influencing health care", "Symptoms; signs; and ill-defined conditions"):
    rows = q(f"""
      select ccs.diag, min(ccs.diag_desc) as d, count(distinct cl.member_id) as members
      from claim_lines cl join ccs on {norm} = ccs.diag
      where ccs.ccs_2_desc like '{lvl2}%'
      group by 1 order by members desc limit 6""")
    show(
        f"top codes in level-2 '{lvl2}' by members",
        [(r[0], r[1][:58], r[2]) for r in rows],
        ["icd", "description", "members"],
    )

print()
print("=" * 30, "E. CCS CARDINALITY BY CHAPTER", "=" * 30)
rows = q(f"""
  with map_side as (
    select ccs_1_desc,
           count(distinct nullif(ccs_2_desc, '')) as l2_cats,
           count(distinct ccs_3_desc) as l3_cats,
           count(*) as codes_in_map
    from ccs group by 1),
  claim_side as (
    select ccs.ccs_1_desc,
           count(*) as claim_rows,
           count(distinct cl.member_id) as members,
           count(distinct ccs.diag) as codes_observed
    from claim_lines cl join ccs on {norm} = ccs.diag
    group by 1)
  select m.ccs_1_desc, m.l2_cats, m.l3_cats, m.codes_in_map,
         coalesce(c.codes_observed, 0) as codes_obs,
         coalesce(c.claim_rows, 0) as claim_rows,
         coalesce(c.members, 0) as members
  from map_side m left join claim_side c using (ccs_1_desc)
  order by members desc""")
show(
    "per level-1 chapter: category/code counts vs observed usage",
    [(r[0][:52], *r[1:]) for r in rows],
    ["chapter", "L2", "L3", "codes_map", "codes_obs", "rows", "members"],
)
tot = q(f"""select count(distinct {norm}) from claim_lines
            where {norm} in (select diag from ccs)""")[0][0]
print(
    f"\ndistinct mapped codes observed overall: {tot:,} of 72,167 in the mapping "
    f"({100 * (1 - tot / 72167):.0f}% of the mapping is never used)"
)
