"""Requirement 1 — characterize member health status from outpatient claims.

Framing (proposed 2026-11-01; justified in reports/2026-11-01_health-status-characterization.md):
a member's health status is the set of CCS level-2 condition categories seen in their
claims, each flagged chronic or one-off, plus light utilization descriptors. Two CCS
level-1 chapters are tracked but never counted as conditions, and unmapped codes form an
explicit bucket. The policy constants here are the single source of truth; the SQL in
sql/ receives them as parameters.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence

import pandas as pd

# Claims dated before this are the documented sentinel/stray rows (1899-2014, ~37 rows);
# null dates (24 rows) are excluded too. Both exclusions are counted, never silent.
CLAIMS_WINDOW_START = dt.date(2015, 1, 1)

# Chronic rule (healthcare-claims skill): a condition is chronic for a member when it is
# coded on >=2 distinct claim dates spanning >=30 days. A single date, or a tight cluster
# of dates, reads as a one-off/acute episode instead — the condition still counts.
CHRONIC_MIN_DATES = 2
CHRONIC_MIN_SPAN_DAYS = 30

# CCS level-1 chapters that never become condition flags. Symptom/Z-code and residual
# rows are kept as per-member utilization context, not as health conditions.
SYMPTOMS_CHAPTER = (
    "Symptoms; signs; and ill-defined conditions and factors influencing health status"
)
RESIDUAL_CHAPTER = "Residual codes; unclassified; all E codes [259. and 260.]"
NON_CONDITION_CHAPTERS = (SYMPTOMS_CHAPTER, RESIDUAL_CHAPTER)

_BRACKET_ID = re.compile(r"\s*\[[^\]]*\]\s*$")


def is_chronic(dates: Sequence[dt.date]) -> bool:
    """Apply the chronic rule to the claim dates a condition was coded on.

    Mirrors the SQL in sql/member_conditions.sql; tests/test_health_status.py asserts
    the two implementations agree.
    """
    distinct = sorted(set(dates))
    if len(distinct) < CHRONIC_MIN_DATES:
        return False
    return (distinct[-1] - distinct[0]).days >= CHRONIC_MIN_SPAN_DAYS


def display_name(ccs2_desc: str) -> str:
    """Human-readable condition name: 'Intestinal infection [135.]' -> 'Intestinal infection'."""
    return _BRACKET_ID.sub("", ccs2_desc).strip()


def render_vignette(
    member_id: str,
    conditions: pd.DataFrame,
    summary: pd.Series,
    max_names: int = 4,
) -> str:
    """Round-trip the characterization into one plain-language sentence.

    `conditions`: this member's rows from member_conditions.parquet (needs columns
    condition, chronic, n_dates). `summary`: their row from member_health_status.parquet.
    """
    ordered = conditions.sort_values(["chronic", "n_dates", "condition"], ascending=False)

    def names(subset: pd.DataFrame) -> str:
        found = subset["condition"].tolist()
        shown = ", ".join(found[:max_names])
        extra = len(found) - max_names
        return f"{shown} (+{extra} more)" if extra > 0 else shown

    chronic_part = names(ordered.loc[ordered["chronic"]])
    acute_part = names(ordered.loc[~ordered["chronic"]])
    bits = []
    if chronic_part:
        bits.append(f"chronic: {chronic_part}")
    if acute_part:
        bits.append(f"one-off: {acute_part}")
    if not bits:
        bits.append("no mappable conditions (symptom/administrative or unmapped codes only)")

    first = pd.Timestamp(summary["first_date"]).strftime("%Y-%m")
    last = pd.Timestamp(summary["last_date"]).strftime("%Y-%m")
    n_days = int(summary["n_claim_days"])
    utilization = f"{n_days} claim day{'s' if n_days != 1 else ''} {first}→{last}"
    extras = []
    if summary["n_symptom_days"] > 0:
        extras.append(f"{int(summary['n_symptom_days'])} of them symptom/administrative")
    if summary["n_unmapped_lines"] > 0:
        extras.append(f"{int(summary['n_unmapped_lines'])} unmapped lines")
    tail = f" ({'; '.join(extras)})" if extras else ""
    return f"Member {member_id} — {'; '.join(bits)}; {utilization}{tail}."
