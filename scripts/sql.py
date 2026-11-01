"""Run duckdb SQL against the project tables.

Views are registered for every table found, parquet cache preferred over raw CSV:
  ccs, claim_lines, prescription_drugs

Usage:
  python scripts/sql.py "select ccs_1_desc, count(*) from ccs group by 1 order by 2 desc"
  python scripts/sql.py -f sql/ccs_level1_counts.sql
"""

from __future__ import annotations

import sys
from pathlib import Path

from oscar_cs.db import connect_views


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    query = Path(args[1]).read_text() if args[0] == "-f" else " ".join(args)
    con = connect_views()
    tables = [r[0] for r in con.execute("show tables").fetchall()]
    print(f"-- views: {', '.join(tables) or '(none - no data yet)'}")
    con.sql(query).show(max_rows=50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
