-- One row per member x CCS level-2 condition, with the chronic flag.
-- Runs against the claims_mapped temp table built from sql/claims_clean_mapped.sql.
-- Chronic rule parameters ($chronic_min_dates, $chronic_min_span_days) come from
-- src/oscar_cs/health_status.py; is_chronic() there mirrors this expression and
-- tests/test_health_status.py asserts they agree.
select
    member_id,
    ccs_1_desc as chapter,
    ccs_2_desc,
    count(*) as n_lines,
    count(distinct date_svc) as n_dates,
    min(date_svc) as first_date,
    max(date_svc) as last_date,
    (
        count(distinct date_svc) >= $chronic_min_dates
        and date_diff('day', min(date_svc), max(date_svc)) >= $chronic_min_span_days
    ) as chronic
from claims_mapped
where bucket = 'condition'
group by member_id, ccs_1_desc, ccs_2_desc;
