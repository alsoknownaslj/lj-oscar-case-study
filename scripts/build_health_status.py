"""Build the requirement-1 health-status characterization from claims + CCS.

Pipeline (policy constants in src/oscar_cs/health_status.py, queries in sql/):
  1. counted exclusions: null service dates, pre-window stray rows
  2. normalize ICD-10 and left-join CCS; count unmapped rows/codes (never silent)
  3. bucket rows: condition / symptoms / residual / unmapped
  4. aggregate member x CCS-level-2 conditions with the chronic flag
  5. aggregate per-member summary + profile class
  6. print headline stats + 3 deterministic vignettes; dump stats json

Outputs (local-only, data/ is gitignored):
  data/processed/member_conditions.parquet
  data/processed/member_health_status.parquet
  data/processed/health_status_stats.json

Usage: python scripts/build_health_status.py
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from oscar_cs.data import parse_ccs2_code
from oscar_cs.db import connect_views, read_sql
from oscar_cs.health_status import (
    CHRONIC_MIN_DATES,
    CHRONIC_MIN_SPAN_DAYS,
    CLAIMS_WINDOW_START,
    RESIDUAL_CHAPTER,
    SYMPTOMS_CHAPTER,
    display_name,
    render_vignette,
)
from oscar_cs.paths import DATA_PROCESSED, ROOT

SQL_DIR = ROOT / "sql"


def one(con, query: str, params: dict | None = None) -> int:
    return int(con.execute(query, params or {}).fetchone()[0])


def build_claims_mapped(con) -> dict:
    """Create the claims_mapped temp table; return the counted exclusions."""
    counts = {
        "rows_total": one(con, "select count(*) from claim_lines"),
        "members_total": one(con, "select count(distinct member_id) from claim_lines"),
        "rows_null_date": one(
            con, "select count(*) from claim_lines where try_cast(date_svc as date) is null"
        ),
        "rows_pre_window": one(
            con,
            "select count(*) from claim_lines where try_cast(date_svc as date) < $ws",
            {"ws": CLAIMS_WINDOW_START},
        ),
    }
    con.execute(
        f"create temp table claims_mapped as {read_sql(SQL_DIR / 'claims_clean_mapped.sql')}",
        {
            "window_start": CLAIMS_WINDOW_START,
            "symptoms_chapter": SYMPTOMS_CHAPTER,
            "residual_chapter": RESIDUAL_CHAPTER,
        },
    )
    counts["rows_clean"] = one(con, "select count(*) from claims_mapped")
    counts["members_clean"] = one(con, "select count(distinct member_id) from claims_mapped")
    counts["members_lost_by_cleaning"] = counts["members_total"] - counts["members_clean"]
    counts["window_end"] = str(con.execute("select max(date_svc) from claims_mapped").fetchone()[0])
    return counts


def mapping_stats(con) -> dict:
    bucket_rows = dict(
        con.execute("select bucket, count(*) from claims_mapped group by bucket").fetchall()
    )
    unmapped_codes = one(
        con, "select count(distinct diag_norm) from claims_mapped where bucket = 'unmapped'"
    )
    top_unmapped = con.execute(
        """select diag_norm, count(*) as n from claims_mapped
           where bucket = 'unmapped' group by diag_norm order by n desc, diag_norm limit 5"""
    ).fetchall()
    rows_clean = sum(bucket_rows.values())
    mapped = rows_clean - bucket_rows.get("unmapped", 0)
    # the policy case: what would dominate "top conditions" without the symptoms bucket
    top_symptom_cats = con.execute(
        """select ccs_2_desc, count(distinct member_id) as n from claims_mapped
           where bucket = 'symptoms' group by 1 order by n desc limit 3"""
    ).fetchall()
    return {
        "bucket_rows": {k: int(v) for k, v in bucket_rows.items()},
        "row_map_coverage_pct": round(100 * mapped / rows_clean, 2),
        "unmapped_distinct_codes": unmapped_codes,
        "top_unmapped_codes": [(c, int(n)) for c, n in top_unmapped],
        "top_symptom_categories_by_members": [(d, int(n)) for d, n in top_symptom_cats],
    }


def build_member_tables(con) -> tuple[pd.DataFrame, pd.DataFrame]:
    chronic_params = {
        "chronic_min_dates": CHRONIC_MIN_DATES,
        "chronic_min_span_days": CHRONIC_MIN_SPAN_DAYS,
    }
    conditions = con.execute(read_sql(SQL_DIR / "member_conditions.sql"), chronic_params).df()
    assert not (conditions["ccs_2_desc"].str.strip() == "").any(), (
        "blank level-2 desc outside the Residual chapter — policy assumption broken"
    )
    conditions["ccs2_id"] = parse_ccs2_code(conditions["ccs_2_desc"])
    conditions["condition"] = conditions["ccs_2_desc"].map(display_name)

    summary = con.execute(read_sql(SQL_DIR / "member_summary.sql")).df()
    sum_cols = ["n_symptom_lines", "n_residual_lines", "n_unmapped_lines"]
    summary[sum_cols] = summary[sum_cols].astype(int)  # duckdb sum() arrives as float
    flags = (
        conditions.groupby("member_id")["chronic"]
        .agg(n_conditions="count", n_chronic="sum")
        .reset_index()
    )
    summary = summary.merge(flags, on="member_id", how="left")
    summary[["n_conditions", "n_chronic"]] = (
        summary[["n_conditions", "n_chronic"]].fillna(0).astype(int)
    )
    summary["n_acute"] = summary["n_conditions"] - summary["n_chronic"]
    summary["profile_class"] = np.select(
        [
            summary["n_chronic"] > 0,
            summary["n_conditions"] > 0,
            (summary["n_symptom_lines"] > 0) | (summary["n_residual_lines"] > 0),
        ],
        ["chronic", "acute_only", "symptom_admin_only"],
        default="unmapped_only",
    )
    return conditions, summary


def population_stats(con, conditions: pd.DataFrame, summary: pd.DataFrame) -> dict:
    members = len(summary)
    prevalence = (
        conditions.groupby(["chapter", "condition"])
        .agg(
            members_any=("member_id", "nunique"),
            members_chronic=("chronic", "sum"),
        )
        .reset_index()
        .sort_values("members_any", ascending=False)
    )
    prevalence["pct_members_any"] = (100 * prevalence["members_any"] / members).round(1)
    dist = summary["n_conditions"].value_counts().sort_index()
    rx_members = one(con, "select count(distinct member_id) from prescription_drugs")
    rx_overlap = one(
        con,
        """select count(*) from
             (select distinct member_id from prescription_drugs) r
             join (select distinct member_id from claims_mapped) c using (member_id)""",
    )
    return {
        "members_characterized": members,
        "member_mix": summary["profile_class"].value_counts().to_dict(),
        "pct_members_chronic": round(100 * (summary["n_chronic"] > 0).mean(), 1),
        "conditions_per_member": {
            "mean": round(summary["n_conditions"].mean(), 2),
            "median": float(summary["n_conditions"].median()),
            "p90": float(summary["n_conditions"].quantile(0.9)),
            "max": int(summary["n_conditions"].max()),
            "distribution": {int(k): int(v) for k, v in dist.items()},
        },
        "top20_conditions": prevalence.head(20).to_dict(orient="records"),
        "rx_members": rx_members,
        "rx_and_claims_members": rx_overlap,
    }


def pick_vignettes(conditions: pd.DataFrame, summary: pd.DataFrame) -> list[tuple[str, str]]:
    """Three deterministic archetypes; selection rules are part of the committed record."""
    indexed = summary.set_index("member_id")

    def render(member_id: str) -> str:
        subset = conditions.loc[conditions["member_id"] == member_id]
        return render_vignette(member_id, subset, indexed.loc[member_id])

    picks: list[tuple[str, str]] = []
    # A — the brief's example shape: chronic cancer plus an injury, few other conditions
    cancer = set(
        conditions.loc[(conditions["chapter"] == "Neoplasms") & conditions["chronic"], "member_id"]
    )
    injury = set(conditions.loc[conditions["chapter"] == "Injury and poisoning", "member_id"])
    tidy = indexed[indexed["n_conditions"].between(2, 4)]
    a_pool = sorted((cancer & injury) & set(tidy.index))
    if a_pool:
        picks.append(("A: cancer + injury", render(a_pool[0])))
    # B — most multimorbid chronic member (exercises the +N more cap)
    most_chronic = summary.sort_values(["n_chronic", "member_id"], ascending=[False, True]).iloc[0][
        "member_id"
    ]
    picks.append(("B: multimorbid chronic", render(most_chronic)))
    # C — healthy-ish: exactly one one-off condition on a single claim day, nothing else
    c_mask = (
        (summary["n_conditions"] == 1)
        & (summary["n_chronic"] == 0)
        & (summary["n_claim_days"] == 1)
        & (summary["n_symptom_lines"] == 0)
        & (summary["n_residual_lines"] == 0)
        & (summary["n_unmapped_lines"] == 0)
    )
    c_pool = summary.loc[c_mask, "member_id"].sort_values()
    if not c_pool.empty:
        picks.append(("C: single one-off", render(c_pool.iloc[0])))
    return picks


def main() -> int:
    con = connect_views()
    views = {r[0] for r in con.execute("show tables").fetchall()}
    missing = {"claim_lines", "ccs", "prescription_drugs"} - views
    if missing:
        print(f"missing tables: {sorted(missing)} — run `make fetch && make cache` first")
        return 1

    stats: dict = {
        "policy": {
            "window_start": str(CLAIMS_WINDOW_START),
            "chronic_rule": f">={CHRONIC_MIN_DATES} dates >={CHRONIC_MIN_SPAN_DAYS} days apart",
            "non_condition_chapters": [SYMPTOMS_CHAPTER, RESIDUAL_CHAPTER],
        }
    }
    stats["exclusions"] = build_claims_mapped(con)
    stats["mapping"] = mapping_stats(con)

    conditions, summary = build_member_tables(con)
    stats["population"] = population_stats(con, conditions, summary)
    vignettes = pick_vignettes(conditions, summary)
    stats["vignettes"] = [{"archetype": a, "text": t} for a, t in vignettes]

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    conditions.to_parquet(DATA_PROCESSED / "member_conditions.parquet", index=False)
    summary.to_parquet(DATA_PROCESSED / "member_health_status.parquet", index=False)
    with open(DATA_PROCESSED / "health_status_stats.json", "w") as fh:
        json.dump(stats, fh, indent=2, default=str)

    print(json.dumps({k: v for k, v in stats.items() if k != "vignettes"}, indent=2, default=str))
    print("\nVignettes (member ids are synthetic; mask in reports):")
    for archetype, text in vignettes:
        print(f"  [{archetype}] {text}")
    print(
        f"\nWrote member_conditions ({len(conditions):,} rows), "
        f"member_health_status ({len(summary):,} rows) to {DATA_PROCESSED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
