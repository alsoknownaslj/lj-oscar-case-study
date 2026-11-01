"""oscar_cs — shared code for the Oscar DS case study."""

from .data import (
    load_ccs,
    load_claim_lines,
    load_prescriptions,
    normalize_icd10,
    parse_ccs2_code,
)
from .paths import DATA_CACHE, DATA_PROCESSED, DATA_RAW, FIGURES, REPORTS, ROOT

__version__ = "0.1.0"

__all__ = [
    "DATA_CACHE",
    "DATA_PROCESSED",
    "DATA_RAW",
    "FIGURES",
    "REPORTS",
    "ROOT",
    "load_ccs",
    "load_claim_lines",
    "load_prescriptions",
    "normalize_icd10",
    "parse_ccs2_code",
]
