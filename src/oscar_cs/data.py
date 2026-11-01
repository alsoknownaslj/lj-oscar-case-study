"""Loaders and code-normalization helpers for the three base tables.

Rules enforced here (see CLAUDE.md "Base tables"):
  - code-like columns stay strings end to end
  - parquet cache preferred over raw CSV
  - ICD-10 joins go through normalize_icd10 on BOTH sides
"""

from __future__ import annotations

import re

import pandas as pd

from .paths import DATA_CACHE, DATA_RAW

_CCS2_CODE = re.compile(r"\[(\d+)\.?\]")


def normalize_icd10(codes: pd.Series | str) -> pd.Series | str:
    """Uppercase, strip whitespace and dots: 'a00.0 ' -> 'A000'.

    Never truncates — unmatched codes should be measured, not forced to match.
    """
    if isinstance(codes, str):
        return codes.strip().upper().replace(".", "")
    return codes.astype("str").str.strip().str.upper().str.replace(".", "", regex=False)


def parse_ccs2_code(desc: pd.Series | str) -> pd.Series | str | None:
    """Extract the numeric CCS id embedded in a level-2 description.

    'Intestinal infection [135.]' -> '135'; returns None/NaN when no bracket id exists
    (~56% of mapping rows have none).
    """
    if isinstance(desc, str):
        m = _CCS2_CODE.search(desc)
        return m.group(1) if m else None
    return desc.astype("str").str.extract(_CCS2_CODE, expand=False)


def _load(table: str, **read_csv_kwargs) -> pd.DataFrame:
    pq = DATA_CACHE / f"{table}.parquet"
    if pq.exists():
        return pd.read_parquet(pq)
    csv = DATA_RAW / f"{table}.csv"
    if csv.exists():
        # dtype=str protects NDC leading zeros and ICD formatting on the raw path
        return pd.read_csv(csv, dtype=str, **read_csv_kwargs)
    raise FileNotFoundError(
        f"{table}: no parquet cache or raw CSV found. Run `make fetch && make cache` "
        "(see CLAUDE.md 'Data status' for the download unblock paths)."
    )


def load_ccs() -> pd.DataFrame:
    """diag (undotted ICD-10) -> diag_desc, ccs_1_desc, ccs_2_desc, ccs_3_desc."""
    return _load("ccs")


def load_claim_lines() -> pd.DataFrame:
    """One row per diagnosis per member per day. Columns unverified until first profile —
    check references/data-dictionary.md, and parse the service-date column explicitly."""
    return _load("claim_lines")


def load_prescriptions() -> pd.DataFrame:
    """One row per filled prescription (NDC + category/group/class). Columns unverified
    until first profile. 371 MB raw — prefer duckdb (scripts/sql.py) for aggregation."""
    return _load("prescription_drugs")
