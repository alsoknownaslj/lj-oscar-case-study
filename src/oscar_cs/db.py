"""Shared duckdb access: one in-memory connection with a view per project table.

Promoted from scripts/sql.py so pipeline scripts and the CLI share one definition of
how tables are read (parquet cache first, raw CSV with explicit quoting as fallback).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from .paths import DATA_CACHE, DATA_RAW

CSV_OPTS = "header = true, all_varchar = true, quote = '\"', escape = '\"'"


def connect_views() -> duckdb.DuckDBPyConnection:
    """In-memory duckdb connection with a view for every table found on disk."""
    con = duckdb.connect()
    names = {p.stem for p in DATA_RAW.glob("*.csv")} | {
        p.stem for p in DATA_CACHE.glob("*.parquet")
    }
    for name in sorted(names):
        pq, csv = DATA_CACHE / f"{name}.parquet", DATA_RAW / f"{name}.csv"
        src = f"read_parquet({str(pq)!r})" if pq.exists() else f"read_csv({str(csv)!r}, {CSV_OPTS})"
        con.execute(f"create or replace view {name} as select * from {src}")
    return con


def read_sql(path: Path | str) -> str:
    """Read a saved query from sql/ (kept there so queries that matter are reviewable)."""
    return Path(path).read_text()
