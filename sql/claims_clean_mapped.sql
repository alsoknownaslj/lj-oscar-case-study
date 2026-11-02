-- Cleaned claim lines joined to CCS, one row per kept claim line, with the policy
-- bucket each row falls in (health status v2). Parameters come from
-- src/oscar_cs/health_status.py via scripts/build_health_status.py (which wraps this
-- in a temp table):
--   $window_start / $window_end   canonical analysis window, both ends inclusive
--   $symptoms_chapter             CCS level-1 chapter split into symptoms vs admin
--   $residual_chapter             CCS level-1 chapter, excluded from conditions
--   $immunizations_level2        level-2 category excluded from conditions
--   $excluded_prefix             code first letter marking admin rows (Z)
-- Buckets: condition | symptoms (non-Z rows of the symptoms chapter: the R-code track)
--   | admin (Z rows of the symptoms chapter) | immunizations | residual | unmapped.
-- Exclusion counts (null dates, out-of-window rows) are printed by the build script.
select
    cl.record_id,
    cl.member_id,
    ccs.ccs_1_desc,
    ccs.ccs_2_desc,
    ccs.ccs_3_desc,
    try_cast(cl.date_svc as date) as date_svc,
    upper(trim(replace(cl.diag1, '.', ''))) as diag_norm,
    case
        when ccs.diag is null then 'unmapped'
        when ccs.ccs_1_desc = $residual_chapter then 'residual'
        when ccs.ccs_2_desc = $immunizations_level2 then 'immunizations'
        when
            ccs.ccs_1_desc = $symptoms_chapter
            and starts_with(upper(trim(replace(cl.diag1, '.', ''))), $excluded_prefix)
            then 'admin'
        when ccs.ccs_1_desc = $symptoms_chapter then 'symptoms'
        else 'condition'
    end as bucket
from claim_lines as cl
left join ccs
    on upper(trim(replace(cl.diag1, '.', ''))) = ccs.diag
where
    try_cast(cl.date_svc as date) is not null
    and try_cast(cl.date_svc as date) between $window_start and $window_end;
