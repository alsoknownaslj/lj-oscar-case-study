"""Materialize data/oscar.duckdb: a self-contained database for IDE browsing.

Base tables are copied in from the parquet cache (no file paths inside, so a DuckDB
IDE extension can open the file as is) and the sql/models/ views are created inside the
database in layer order. Written with STORAGE_VERSION 'v1.0.0' so older readers can open
it (the SQLTools DuckDB driver bundles 1.3.2). Rebuild after model changes: make db.
DuckDB allows one writer, so close a read/write IDE connection first; a read-only
connection should disconnect and reconnect after a rebuild to see fresh data.

Usage: python scripts/build_db.py
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from oscar_cs.db import _layer_rank
from oscar_cs.paths import DATA_CACHE, ROOT, SQL_MODELS

DB_PATH = ROOT / "data" / "oscar.duckdb"
TABLES = ("ccs", "claim_lines", "prescription_drugs")


def main() -> int:
    for path in (DB_PATH, Path(str(DB_PATH) + ".wal")):
        try:
            path.unlink(missing_ok=True)
        except OSError as err:
            print(f"[fail] cannot replace {path.name}: {err}")
            print("       close the database connection in your IDE, then rerun make db")
            return 1

    missing = [t for t in TABLES if not (DATA_CACHE / f"{t}.parquet").exists()]
    if missing:
        print(f"[fail] parquet cache missing {missing} - run `make fetch cache` first")
        return 1

    con = duckdb.connect()
    try:
        con.execute(f"attach {str(DB_PATH)!r} as oscar (storage_version 'v1.0.0')")
    except duckdb.Error:
        print(
            "[warn] this duckdb has no STORAGE_VERSION option; writing the native "
            "format, which older IDE drivers may not open"
        )
        con.execute(f"attach {str(DB_PATH)!r} as oscar")
    con.execute("use oscar")
    for name in TABLES:
        pq = DATA_CACHE / f"{name}.parquet"
        con.execute(f"create table {name} as select * from read_parquet({str(pq)!r})")
    for path in sorted(SQL_MODELS.glob("*.sql"), key=_layer_rank):
        con.execute(f"create view {path.stem} as\n{path.read_text()}")
    inventory = con.sql("""
        select table_type, count(*) as n, string_agg(table_name, ', ' order by table_name) as names
        from information_schema.tables
        where table_catalog = 'oscar'
        group by table_type
        order by table_type
    """).df()
    con.close()
    print(inventory.to_string(index=False))
    print(f"[ok] {DB_PATH.relative_to(ROOT)}: {DB_PATH.stat().st_size / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
