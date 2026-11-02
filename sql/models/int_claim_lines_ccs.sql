-- Claim lines enriched with all three CCS levels via the normalized ICD-10 join.
-- Left join: unmapped codes stay, flagged (is_mapped = false); the 99.89% row coverage
-- is measured off this view. in_overlap marks the claims/rx overlap window.
select
    cl.record_id,
    cl.member_id,
    cl.date_svc,
    cl.diag1,
    cl.diag_norm,
    cl.date_is_missing,
    cl.date_pre_2015,
    cl.is_clean,
    ccs.ccs_1_desc,
    ccs.ccs_2_desc,
    ccs.ccs_2_id,
    ccs.ccs_3_desc,
    ccs.diag_norm is not null as is_mapped,
    coalesce(cl.date_svc between date '2015-12-01' and date '2018-06-30', false) as in_overlap
from stg_claim_lines as cl
left join stg_ccs as ccs on cl.diag_norm = ccs.diag_norm
