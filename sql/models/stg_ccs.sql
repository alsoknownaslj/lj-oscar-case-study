-- CCS mapping keyed by normalized (undotted, uppercase) ICD-10-CM code.
-- ccs_2_desc is blank exactly for the 7,621 Residual-chapter codes -> null here,
-- bucketed explicitly downstream. ccs_2_id parses the embedded bracket id
-- ('Intestinal infection [135.]' -> '135'), mirroring oscar_cs.data.parse_ccs2_code.
select
    diag_desc,
    ccs_1_desc,
    ccs_3_desc,
    upper(trim(diag)) as diag_norm,
    nullif(trim(ccs_2_desc), '') as ccs_2_desc,
    nullif(regexp_extract(ccs_2_desc, '\[(\d+)\.?\]', 1), '') as ccs_2_id
from ccs
