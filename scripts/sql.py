"""Run duckdb SQL against the project tables and models.

Views are registered for every base table (parquet cache preferred over raw CSV) plus
the layered models in sql/models/ (stg_* -> int_* -> dim_* -> fct_*):
  ccs, claim_lines, prescription_drugs, stg_*, int_*, ...

Usage:
  python scripts/sql.py "select ccs_1_desc, count(*) from stg_ccs group by 1 order by 2 desc"
  python scripts/sql.py -f sql/ccs_level1_counts.sql
"""

from __future__ import annotations

import sys
from pathlib import Path

from oscar_cs.db import connect


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    query = Path(args[1]).read_text() if args[0] == "-f" else " ".join(args)
    con = connect()
    tables = [r[0] for r in con.execute("show tables").fetchall()]
    print(f"-- views: {', '.join(tables) or '(none - no data yet)'}")
    con.sql(query).show(max_rows=50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
