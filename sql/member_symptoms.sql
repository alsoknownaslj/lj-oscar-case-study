-- One row per member x CCS level-3 symptom (the R-code track: non-Z rows of the
-- symptoms chapter). Same shape expression as member_conditions.sql; the build script
-- renames chronic -> persistent for this track ("symptoms that could mean something",
-- never conditions). Runs against the claims_mapped temp table.
select
    member_id,
    ccs_3_desc as symptom,
    count(*) as n_lines,
    count(distinct date_svc) as n_dates,
    min(date_svc) as first_date,
    max(date_svc) as last_date,
    date_diff('day', min(date_svc), max(date_svc)) as span_days,
    case
        when count(distinct date_svc) = 1 then 'one_off'
        when date_diff('day', min(date_svc), max(date_svc)) <= $episode_max_span_days
            then 'episode'
        else 'persistent'
    end as shape
from claims_mapped
where bucket = 'symptoms'
group by member_id, ccs_3_desc;
