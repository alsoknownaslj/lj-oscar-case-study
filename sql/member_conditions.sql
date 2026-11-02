-- One row per member x CCS level-2 condition, with the v2 shape over distinct claim
-- dates: one_off (1 date) | episode (>=2 dates, span <= $episode_max_span_days)
-- | chronic (span beyond that). The reinfection-trap cap (injuries/infections never
-- chronic) is applied in Python, where the scope list lives; this file reports the
-- uncapped shape. classify_shape() in src/oscar_cs/health_status.py mirrors this
-- expression and tests/test_health_status.py asserts the two agree.
-- Runs against the claims_mapped temp table built from sql/claims_clean_mapped.sql.
select
    member_id,
    ccs_1_desc as chapter,
    ccs_2_desc,
    count(*) as n_lines,
    count(distinct date_svc) as n_dates,
    min(date_svc) as first_date,
    max(date_svc) as last_date,
    date_diff('day', min(date_svc), max(date_svc)) as span_days,
    case
        when count(distinct date_svc) = 1 then 'one_off'
        when date_diff('day', min(date_svc), max(date_svc)) <= $episode_max_span_days
            then 'episode'
        else 'chronic'
    end as shape_raw
from claims_mapped
where bucket = 'condition'
group by member_id, ccs_1_desc, ccs_2_desc;
