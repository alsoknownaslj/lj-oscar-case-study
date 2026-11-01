-- How many diagnosis codes fall in each CCS level-1 chapter?
-- Run: python scripts/sql.py -f sql/ccs_level1_counts.sql
select
    ccs_1_desc,
    count(*) as n_codes
from ccs
group by ccs_1_desc
order by n_codes desc;
