"""Unit tests for the requirement-1 v2 characterization logic (no data files needed)."""

import datetime as dt

import duckdb
import pandas as pd
import pytest

from oscar_cs.health_status import (
    EPISODE_MAX_SPAN_DAYS,
    assign_tier,
    classify_shape,
    display_name,
    head_tail_cuts,
    is_acute_only,
    render_vignette,
)

D = dt.date

SHAPE_CASES = [
    ([D(2016, 1, 1)], "one_off"),
    ([D(2016, 1, 1), D(2016, 1, 1)], "one_off"),  # duplicates collapse
    ([D(2016, 1, 1), D(2016, 6, 29)], "episode"),  # span 180 — boundary stays episode
    ([D(2016, 1, 1), D(2016, 6, 30)], "chronic"),  # span 181
    ([D(2016, 6, 30), D(2016, 1, 1)], "chronic"),  # unsorted input
    ([D(2016, 1, 1), D(2016, 2, 1), D(2016, 3, 1)], "episode"),  # bounded arc
]


def test_classify_shape():
    for dates, expected in SHAPE_CASES:
        assert classify_shape(dates) == expected, dates


def test_classify_shape_acute_only_caps_chronic():
    long_span = [D(2016, 1, 1), D(2017, 1, 1)]
    assert classify_shape(long_span) == "chronic"
    assert classify_shape(long_span, acute_only=True) == "episode"
    assert classify_shape([D(2016, 1, 1)], acute_only=True) == "one_off"


def test_classify_shape_rejects_empty():
    with pytest.raises(ValueError):
        classify_shape([])


def test_sql_shape_expression_matches_python():
    # Mirrors the expression in sql/member_conditions.sql; both must stay in sync.
    con = duckdb.connect()
    for dates, expected in SHAPE_CASES:
        values = ", ".join(f"(DATE '{d}')" for d in dates)
        got = con.execute(
            f"""select case
                  when count(distinct d) = 1 then 'one_off'
                  when date_diff('day', min(d), max(d)) <= {EPISODE_MAX_SPAN_DAYS}
                      then 'episode'
                  else 'chronic'
                end
                from (values {values}) t(d)"""
        ).fetchone()[0]
        assert got == expected, dates


def test_is_acute_only():
    assert is_acute_only("Injury and poisoning", "Fractures")
    assert is_acute_only("Infectious and parasitic diseases", "Bacterial infection")
    # Viral infection is exempt on purpose: HIV/hepatitis live inside it
    assert not is_acute_only("Infectious and parasitic diseases", "Viral infection")
    assert not is_acute_only("Diseases of the circulatory system", "Essential hypertension")


def test_head_tail_cuts_and_tiers():
    # positives: [1,1,1,1,8,8,20,40] -> cut1 = 10, above-cut1 mean = 30
    values = pd.Series([0, 0, 1, 1, 1, 1, 8, 8, 20, 40])
    cut1, cut2 = head_tail_cuts(values)
    assert cut1 == 10.0
    assert cut2 == 30.0
    tiers = assign_tier(values, cut1, cut2)
    assert tiers.tolist() == ["none"] * 2 + ["low"] * 6 + ["med", "high"]


def test_head_tail_cuts_ties_cannot_collapse_tiers():
    # the quartile failure mode: heavy ties at 1 — head/tail still yields 3 bins
    values = pd.Series([1] * 90 + [10] * 9 + [100])
    cut1, cut2 = head_tail_cuts(values)
    assert cut1 < 10 < cut2 < 100
    tiers = assign_tier(values, cut1, cut2)
    assert set(tiers) == {"low", "med", "high"}


def test_head_tail_cuts_needs_positives():
    with pytest.raises(ValueError):
        head_tail_cuts(pd.Series([0, 0]))


def test_display_name():
    assert display_name("Intestinal infection [135.]") == "Intestinal infection"
    assert display_name("Essential hypertension") == "Essential hypertension"
    assert display_name("Residual codes; unclassified; all E codes [259. and 260.]") == (
        "Residual codes; unclassified; all E codes"
    )


def _summary(**overrides) -> pd.Series:
    base = {
        "first_date": dt.date(2016, 1, 5),
        "last_date": dt.date(2018, 5, 2),
        "n_claim_days": 23,
        "n_symptom_days": 4,
        "symptoms_persistent": True,
        "n_admin_lines": 3,
        "n_unmapped_lines": 0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_render_vignette_caps_and_labels():
    conditions = pd.DataFrame(
        {
            "member_id": ["M1"] * 7,
            "condition": [f"Cond {i}" for i in range(5)] + ["Fractures", "Viral infection"],
            "shape": ["chronic"] * 5 + ["episode", "one_off"],
            "n_dates": [9, 8, 7, 6, 5, 3, 1],
        }
    )
    text = render_vignette("A", conditions, _summary())
    assert text.startswith("Member A")
    assert "chronic: Cond 0, Cond 1, Cond 2, Cond 3 (+1 more)" in text
    assert "episodes: Fractures" in text
    assert "one-off: Viral infection" in text
    assert "symptoms on 4 days (persistent)" in text
    assert "23 claim days 2016-01→2018-05" in text
    assert "3 administrative lines" in text


def test_render_vignette_no_conditions():
    conditions = pd.DataFrame({"member_id": [], "condition": [], "shape": [], "n_dates": []})
    summary = _summary(
        last_date=dt.date(2016, 1, 5),
        n_claim_days=1,
        n_symptom_days=1,
        symptoms_persistent=False,
        n_admin_lines=0,
    )
    text = render_vignette("B", conditions, summary)
    assert "no conditions" in text
    assert "symptoms on 1 day" in text
    assert "(persistent)" not in text
    assert "1 claim day 2016-01→2016-01" in text  # singular, not "1 claim days"
