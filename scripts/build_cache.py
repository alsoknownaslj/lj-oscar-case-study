"""Build faithful parquet mirrors of the raw CSVs in data/cache/.

All columns are kept as VARCHAR on purpose: diagnosis codes and NDCs must never be
type-inferred into integers (leading zeros, scientific notation). Loaders in
src/oscar_cs/data.py cast dates/numerics explicitly where needed.

Usage: python scripts/build_cache.py [table ...]   (default: every CSV in data/raw/)
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "cache"


def build(csv_path: Path) -> None:
    out = CACHE / (csv_path.stem + ".parquet")
    con = duckdb.connect()
    con.execute(
        f"""
        copy (
            select * from read_csv(
                {str(csv_path)!r}, header = true, all_varchar = true, quote = '"', escape = '"'
            )
        ) to {str(out)!r} (format parquet, compression zstd)
        """
    )
    rows = con.execute(f"select count(*) from read_parquet({str(out)!r})").fetchone()[0]
    print(f"[ok] {out.name}: {rows:,} rows, {out.stat().st_size / 1e6:.1f} MB")


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:]
    csvs = [
        p for p in sorted(RAW.glob("*.csv")) if not wanted or p.stem in wanted or p.name in wanted
    ]
    if not csvs:
        print("No CSVs found in data/raw/ - run `make fetch` first (see CLAUDE.md).")
        return 1
    for p in csvs:
        build(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
