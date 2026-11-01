-- Cleaned claim lines joined to CCS, one row per kept claim line, with the policy
-- bucket each row falls in. Parameters come from src/oscar_cs/health_status.py via
-- scripts/build_health_status.py (which wraps this in a temp table):
--   $window_start      first valid service date (earlier rows are documented strays)
--   $symptoms_chapter  CCS level-1 chapter tracked but never a condition
--   $residual_chapter  CCS level-1 chapter tracked but never a condition
-- Exclusion counts (null dates, pre-window rows) are printed by the build script.
select
    cl.record_id,
    cl.member_id,
    ccs.ccs_1_desc,
    ccs.ccs_2_desc,
    try_cast(cl.date_svc as date) as date_svc,
    upper(trim(replace(cl.diag1, '.', ''))) as diag_norm,
    case
        when ccs.diag is null then 'unmapped'
        when ccs.ccs_1_desc = $residual_chapter then 'residual'
        when ccs.ccs_1_desc = $symptoms_chapter then 'symptoms'
        else 'condition'
    end as bucket
from claim_lines as cl
left join ccs
    on upper(trim(replace(cl.diag1, '.', ''))) = ccs.diag
where
    try_cast(cl.date_svc as date) is not null
    and try_cast(cl.date_svc as date) >= $window_start;
