"""Unit tests for the requirement-1 characterization logic (no data files needed)."""

import datetime as dt

import duckdb
import pandas as pd

from oscar_cs.health_status import (
    CHRONIC_MIN_DATES,
    CHRONIC_MIN_SPAN_DAYS,
    display_name,
    is_chronic,
    render_vignette,
)

D = dt.date

CHRONIC_CASES = [
    ([], False),
    ([D(2016, 1, 1)], False),
    ([D(2016, 1, 1), D(2016, 1, 30)], False),  # 29 days apart — one short
    ([D(2016, 1, 1), D(2016, 1, 31)], True),  # exactly 30 days apart
    ([D(2016, 1, 1), D(2016, 1, 1), D(2016, 1, 1)], False),  # duplicates collapse
    ([D(2016, 3, 1), D(2016, 1, 1), D(2016, 1, 10)], True),  # unsorted input
]


def test_is_chronic():
    for dates, expected in CHRONIC_CASES:
        assert is_chronic(dates) is expected, dates


def test_sql_chronic_expression_matches_python():
    # Mirrors the expression in sql/member_conditions.sql; both must stay in sync.
    con = duckdb.connect()
    for dates, expected in CHRONIC_CASES:
        if not dates:
            continue  # group-by never produces an empty group
        values = ", ".join(f"(DATE '{d}')" for d in dates)
        got = con.execute(
            f"""select count(distinct d) >= {CHRONIC_MIN_DATES}
                and date_diff('day', min(d), max(d)) >= {CHRONIC_MIN_SPAN_DAYS}
                from (values {values}) t(d)"""
        ).fetchone()[0]
        assert got is expected, dates


def test_display_name():
    assert display_name("Intestinal infection [135.]") == "Intestinal infection"
    assert display_name("Essential hypertension") == "Essential hypertension"
    assert display_name("Residual codes; unclassified; all E codes [259. and 260.]") == (
        "Residual codes; unclassified; all E codes"
    )


def test_render_vignette_caps_and_labels():
    conditions = pd.DataFrame(
        {
            "member_id": ["M1"] * 6,
            "condition": [f"Cond {i}" for i in range(5)] + ["Fracture of lower limb"],
            "chronic": [True] * 5 + [False],
            "n_dates": [9, 8, 7, 6, 5, 1],
        }
    )
    summary = pd.Series(
        {
            "first_date": dt.date(2016, 1, 5),
            "last_date": dt.date(2018, 11, 2),
            "n_claim_days": 23,
            "n_symptom_days": 4,
            "n_unmapped_lines": 0,
        }
    )
    text = render_vignette("M1", conditions, summary)
    assert text.startswith("Member M1")
    assert "chronic: Cond 0, Cond 1, Cond 2, Cond 3 (+1 more)" in text
    assert "one-off: Fracture of lower limb" in text
    assert "23 claim days 2016-01→2018-11" in text
    assert "4 of them symptom/administrative" in text


def test_render_vignette_no_conditions():
    conditions = pd.DataFrame({"member_id": [], "condition": [], "chronic": [], "n_dates": []})
    summary = pd.Series(
        {
            "first_date": dt.date(2017, 3, 1),
            "last_date": dt.date(2017, 3, 1),
            "n_claim_days": 1,
            "n_symptom_days": 1,
            "n_unmapped_lines": 0,
        }
    )
    text = render_vignette("M2", conditions, summary)
    assert "no mappable conditions" in text
    assert "1 claim day 2017-03→2017-03" in text  # singular, not "1 claim days"
