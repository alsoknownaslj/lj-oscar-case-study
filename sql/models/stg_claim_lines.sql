-- Cleaned claim lines: typed columns + exclusion flags. One row = one diagnosis x
-- member x service date. No row is dropped here; downstream models filter on is_clean
-- so every exclusion stays countable.
select
    record_id,
    member_id,
    diag1,
    try_cast(date_svc as date) as date_svc,
    upper(trim(replace(diag1, '.', ''))) as diag_norm,
    try_cast(date_svc as date) is null as date_is_missing,
    coalesce(try_cast(date_svc as date) < date '2015-01-01', false) as date_pre_2015,
    coalesce(try_cast(date_svc as date) >= date '2015-01-01', false) as is_clean
from claim_lines
