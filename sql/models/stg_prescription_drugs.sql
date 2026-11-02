-- Typed prescription fills. No known dirty rows (window 2013-12 to 2018-06, no nulls).
-- fill_month is the persistence unit (distinct year-months with a fill); in_overlap
-- marks the claims/rx overlap window (2015-12 to 2018-06).
select
    record_id,
    member_id,
    ndc,
    drug_category,
    drug_group,
    drug_class,
    try_cast(date_svc as date) as date_svc,
    -- explicit cast: date_trunc returns TIMESTAMP on older duckdb and DATE on newer,
    -- and a version-stable type keeps the view readable from the IDE's bundled engine
    cast(date_trunc('month', try_cast(date_svc as date)) as date) as fill_month,
    coalesce(
        try_cast(date_svc as date) between date '2015-12-01' and date '2018-06-30', false
    ) as in_overlap
from prescription_drugs
