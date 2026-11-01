"""Smoke tests. Pure-function tests always run; data tests skip until files land."""

import pandas as pd
import pytest

from oscar_cs import load_ccs, normalize_icd10, parse_ccs2_code
from oscar_cs.paths import DATA_RAW, REFERENCES


def test_normalize_icd10_scalar():
    assert normalize_icd10(" a00.0 ") == "A000"
    assert normalize_icd10("A0100") == "A0100"


def test_normalize_icd10_series():
    s = pd.Series(["a00.0", " J09.X1 ", "A000"])
    assert normalize_icd10(s).tolist() == ["A000", "J09X1", "A000"]


def test_parse_ccs2_code():
    assert parse_ccs2_code("Intestinal infection [135.]") == "135"
    assert parse_ccs2_code("Intestinal infection") is None
    s = pd.Series(["Foo [12.]", "Bar"])
    out = parse_ccs2_code(s)
    assert out.iloc[0] == "12" and pd.isna(out.iloc[1])


def test_committed_ccs_sample_schema():
    df = pd.read_csv(REFERENCES / "samples" / "ccs_sample.csv", dtype=str)
    assert list(df.columns) == ["diag", "diag_desc", "ccs_1_desc", "ccs_2_desc", "ccs_3_desc"]
    assert not df["diag"].str.contains(".", regex=False).any(), "ccs.diag must be undotted"
    assert df["diag"].str.len().between(3, 7).all()


@pytest.mark.skipif(not (DATA_RAW / "ccs.csv").exists(), reason="raw data not downloaded yet")
def test_load_ccs_full():
    df = load_ccs()
    assert len(df) > 50_000
    assert df["diag"].is_unique
