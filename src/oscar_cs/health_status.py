"""Requirement 1 — characterize member health status from outpatient claims.

Health status v2 (Lauren ratified 2026-11-02; rules in memory/decisions.md):
a member's health status is the set of CCS level-2 conditions seen in their in-window
claims, each shaped one-off / episode / chronic from its claim-date pattern, plus an
R-code symptoms track, utilization tiers (head/tail breaks), and a >p99 high-utilizer
flag. Z-codes, immunizations/screening, the Residual chapter and unmapped codes are
excluded from conditions (each a counted bucket). The policy constants here are the
single source of truth; the SQL in sql/ receives them as parameters.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence

import pandas as pd

# Claims dated before this are the documented sentinel/stray rows (1899-2014, ~38 rows);
# null dates (24 rows) are excluded too. Both exclusions are counted, never silent.
CLAIMS_WINDOW_START = dt.date(2015, 1, 1)

# Canonical cross-table analysis window (Lauren, 2026-11-02): the intersection of the two
# tables' real coverage. Rx reaches back to 2013-12 (left-censored vs claims, 10.4% of
# fills) and BOTH feeds taper out together over Apr-May 2018 - the claims max of
# 2018-12-06 is 6 stray rows, not coverage. Population and linkage stats use this window;
# pre-window rx may serve only as explicitly labeled history, never silently.
ANALYSIS_WINDOW_START = dt.date(2015, 9, 1)
ANALYSIS_WINDOW_END = dt.date(2018, 6, 4)

# Shape rule (health status v2): per member x condition, over distinct claim dates —
#   one_off   1 distinct date
#   episode   >=2 dates, total span <= EPISODE_MAX_SPAN_DAYS (a bounded arc of care)
#   chronic   span > EPISODE_MAX_SPAN_DAYS (ongoing or recurring contact)
# Replaces the 11-01 rule (>=2 dates >=30d apart), 44% of whose "chronic" were arcs.
EPISODE_MAX_SPAN_DAYS = 180

# Reinfection trap (v2): infections and injuries that keep coming back are repeat
# episodes, never chronic — their shape is capped at 'episode'. Scope: the Injury
# chapter plus the infection level-2 categories (display_name form, brackets stripped).
# "Viral infection" is exempt on purpose: HIV and hepatitis live inside it as level-3s.
# Known cost (for the report): tuberculosis sits in "Bacterial infection" and spinal
# cord injury in the Injury chapter, so neither can read chronic.
INJURY_CHAPTER = "Injury and poisoning"
ACUTE_ONLY_CONDITIONS = frozenset(
    {
        "Bacterial infection",
        "Mycoses",
        "Other infections; including parasitic",
        "Respiratory infections",
        "Intestinal infection",
        "Central nervous system infection",
        "Skin and subcutaneous tissue infections",
    }
)

# CCS level-1 chapters that never become condition flags.
SYMPTOMS_CHAPTER = (
    "Symptoms; signs; and ill-defined conditions and factors influencing health status"
)
RESIDUAL_CHAPTER = "Residual codes; unclassified; all E codes [259. and 260.]"
NON_CONDITION_CHAPTERS = (SYMPTOMS_CHAPTER, RESIDUAL_CHAPTER)

# Inside the symptoms chapter the split is by first letter of the normalized code
# (matches the EDA's R/Z definition): Z-codes are administrative (excluded); everything
# else is the symptoms track — "symptoms that could mean something" (Lauren), kept per
# member but never a condition. Immunizations/screening is excluded by level-2 name.
EXCLUDED_CODE_PREFIX = "Z"
IMMUNIZATIONS_LEVEL2 = "Immunizations and screening for infectious disease [10.]"

_BRACKET_ID = re.compile(r"\s*\[[^\]]*\]\s*$")


def classify_shape(dates: Sequence[dt.date], acute_only: bool = False) -> str:
    """Shape a member x condition pair from the claim dates it was coded on.

    Mirrors the SQL expression in sql/member_conditions.sql; tests assert agreement.
    """
    distinct = sorted(set(dates))
    if not distinct:
        raise ValueError("a pair with no dates cannot be shaped")
    if len(distinct) == 1:
        return "one_off"
    span = (distinct[-1] - distinct[0]).days
    if span <= EPISODE_MAX_SPAN_DAYS or acute_only:
        return "episode"
    return "chronic"


def is_acute_only(chapter: str, condition: str) -> bool:
    """True when the reinfection-trap cap applies (condition in display_name form)."""
    return chapter == INJURY_CHAPTER or condition in ACUTE_ONLY_CONDITIONS


def head_tail_cuts(values: Sequence[float]) -> tuple[float, float]:
    """Head/tail-breaks cut points over the positive values (zeros are their own tier).

    cut1 = mean of the positive values; cut2 = mean of the values above cut1. Built for
    heavy-tailed counts: cuts are means, so tied integers cannot collapse a tier (the
    documented quartile failure).
    """
    s = pd.Series(values, dtype="float64")
    positive = s[s > 0]
    if positive.empty:
        raise ValueError("head/tail breaks need at least one positive value")
    cut1 = float(positive.mean())
    above = positive[positive > cut1]
    cut2 = float(above.mean()) if not above.empty else cut1
    return cut1, cut2


def assign_tier(values: pd.Series, cut1: float, cut2: float) -> pd.Series:
    """Map counts to none / low / med / high given head/tail cut points."""
    tiers = pd.Series("none", index=values.index, dtype="str")
    tiers[values > 0] = "low"
    tiers[values > cut1] = "med"
    tiers[values > cut2] = "high"
    return tiers


def display_name(ccs2_desc: str) -> str:
    """Human-readable condition name: 'Intestinal infection [135.]' -> 'Intestinal infection'."""
    return _BRACKET_ID.sub("", ccs2_desc).strip()


SHAPE_LABELS = {"chronic": "chronic", "episode": "episodes", "one_off": "one-off"}


def render_vignette(
    member_label: str,
    conditions: pd.DataFrame,
    summary: pd.Series,
    max_names: int = 4,
) -> str:
    """Round-trip the characterization into one plain-language sentence.

    `conditions`: this member's rows from member_conditions.parquet (needs columns
    condition, shape, n_dates). `summary`: their row from member_health_status.parquet.
    Pass a masked label (never a raw member id) when the text may land in a report.
    """
    order = {"chronic": 0, "episode": 1, "one_off": 2}
    ordered = conditions.sort_values(
        ["shape", "n_dates", "condition"],
        ascending=[True, False, True],
        key=lambda col: col.map(order) if col.name == "shape" else col,
    )

    def names(subset: pd.DataFrame) -> str:
        found = subset["condition"].tolist()
        shown = ", ".join(found[:max_names])
        extra = len(found) - max_names
        return f"{shown} (+{extra} more)" if extra > 0 else shown

    bits = []
    for shape, label in SHAPE_LABELS.items():
        part = names(ordered.loc[ordered["shape"] == shape])
        if part:
            bits.append(f"{label}: {part}")
    if not bits:
        bits.append("no conditions (symptom, administrative or unmapped codes only)")
    if summary["n_symptom_days"] > 0:
        persistence = " (persistent)" if summary["symptoms_persistent"] else ""
        n_sym = int(summary["n_symptom_days"])
        bits.append(f"symptoms on {n_sym} day{'s' if n_sym != 1 else ''}{persistence}")

    first = pd.Timestamp(summary["first_date"]).strftime("%Y-%m")
    last = pd.Timestamp(summary["last_date"]).strftime("%Y-%m")
    n_days = int(summary["n_claim_days"])
    utilization = f"{n_days} claim day{'s' if n_days != 1 else ''} {first}→{last}"
    extras = []
    n_admin = int(summary["n_admin_lines"])
    if n_admin > 0:
        extras.append(f"{n_admin} administrative line{'s' if n_admin != 1 else ''}")
    n_unmapped = int(summary["n_unmapped_lines"])
    if n_unmapped > 0:
        extras.append(f"{n_unmapped} unmapped line{'s' if n_unmapped != 1 else ''}")
    tail = f" ({'; '.join(extras)})" if extras else ""
    return f"Member {member_label} — {'; '.join(bits)}; {utilization}{tail}."
