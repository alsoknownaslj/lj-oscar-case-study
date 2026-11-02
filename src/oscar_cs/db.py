"""One duckdb connection for the whole project: base views plus layered sql/ models.

Base views (ccs, claim_lines, prescription_drugs) read the parquet cache first and fall
back to raw CSV with explicit quote settings (the claims file has quoted fields deep
inside; sniffing breaks at row ~1.78M). Files in sql/models/ hold a single SELECT each;
every file becomes a view named after it, created in dbt layer order:
stg_* -> int_* -> dim_* -> fct_*. Within a layer, models must not depend on each other.
connect_views() gives the base views alone (what the EDA scripts and the requirement-1
pipeline use); read_sql() loads a saved query from sql/.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from .paths import DATA_CACHE, DATA_RAW, SQL_MODELS

_CSV_OPTS = "header = true, all_varchar = true, quote = '\"', escape = '\"'"
_LAYER_ORDER = {"stg": 0, "int": 1, "dim": 2, "fct": 3}


def _layer_rank(path: Path) -> tuple[int, str]:
    prefix = path.stem.split("_", 1)[0]
    return (_LAYER_ORDER.get(prefix, 99), path.stem)


def connect(models: bool = True) -> duckdb.DuckDBPyConnection:
    """In-memory duckdb with base views and, by default, the sql/models/ views."""
    con = duckdb.connect()
    names = {p.stem for p in DATA_RAW.glob("*.csv")} | {
        p.stem for p in DATA_CACHE.glob("*.parquet")
    }
    for name in sorted(names):
        pq, csv = DATA_CACHE / f"{name}.parquet", DATA_RAW / f"{name}.csv"
        src = (
            f"read_parquet({str(pq)!r})" if pq.exists() else f"read_csv({str(csv)!r}, {_CSV_OPTS})"
        )
        con.execute(f"create or replace view {name} as select * from {src}")
    if models and SQL_MODELS.is_dir():
        for path in sorted(SQL_MODELS.glob("*.sql"), key=_layer_rank):
            con.execute(f"create or replace view {path.stem} as\n{path.read_text()}")
    return con


def connect_views() -> duckdb.DuckDBPyConnection:
    """Base views only - what the EDA scripts and the requirement-1 pipeline use."""
    return connect(models=False)


def read_sql(path: Path | str) -> str:
    """Read a saved query from sql/ (kept there so queries that matter are reviewable)."""
    return Path(path).read_text()
