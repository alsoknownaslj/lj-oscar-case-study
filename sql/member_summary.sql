-- One row per member with >=1 kept in-window claim line: utilization descriptors plus
-- how much of their history falls in each v2 policy bucket. Condition/symptom counts
-- and tiers are joined on afterwards by scripts/build_health_status.py.
-- Runs against the claims_mapped temp table built from sql/claims_clean_mapped.sql.
select
    member_id,
    count(*) as n_lines,
    count(distinct date_svc) as n_claim_days,
    min(date_svc) as first_date,
    max(date_svc) as last_date,
    date_diff('day', min(date_svc), max(date_svc)) as span_days,
    count(distinct case when bucket = 'symptoms' then date_svc end) as n_symptom_days,
    sum(case when bucket = 'symptoms' then 1 else 0 end) as n_symptom_lines,
    sum(case when bucket = 'admin' then 1 else 0 end) as n_admin_lines,
    sum(case when bucket = 'immunizations' then 1 else 0 end) as n_immunization_lines,
    sum(case when bucket = 'residual' then 1 else 0 end) as n_residual_lines,
    sum(case when bucket = 'unmapped' then 1 else 0 end) as n_unmapped_lines
from claims_mapped
group by member_id;
