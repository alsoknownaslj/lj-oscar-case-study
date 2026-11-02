"""Canonical project paths. Import these; never hardcode paths in analysis code."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_CACHE = ROOT / "data" / "cache"
DATA_PROCESSED = ROOT / "data" / "processed"
SQL_MODELS = ROOT / "sql" / "models"
REFERENCES = ROOT / "references"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
