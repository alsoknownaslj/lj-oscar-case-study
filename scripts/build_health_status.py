"""Build the requirement-1 health-status characterization (v2) from claims + CCS.

Pipeline (policy constants in src/oscar_cs/health_status.py, queries in sql/):
  1. counted exclusions: null service dates, rows outside the canonical window
  2. normalize ICD-10 and left-join CCS; count unmapped rows/codes (never silent)
  3. bucket rows: condition / symptoms (R-code track) / admin (Z) / immunizations
     / residual / unmapped
  4. shape member x CCS-level-2 conditions (one_off / episode / chronic) with the
     reinfection-trap cap, and member x level-3 symptoms (persistent, never chronic)
  5. utilization tiers via head/tail breaks (dx lines, rx fills; zero its own bin),
     >p99 high-utilizer flags, and the dx x rx tier contingency with lift
  6. print headline stats + 3 deterministic masked vignettes; dump stats json

Outputs (local-only, data/ is gitignored):
  data/processed/member_conditions.parquet
  data/processed/member_symptoms.parquet
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
    ANALYSIS_WINDOW_END,
    ANALYSIS_WINDOW_START,
    EPISODE_MAX_SPAN_DAYS,
    EXCLUDED_CODE_PREFIX,
    IMMUNIZATIONS_LEVEL2,
    RESIDUAL_CHAPTER,
    SYMPTOMS_CHAPTER,
    assign_tier,
    display_name,
    head_tail_cuts,
    is_acute_only,
    render_vignette,
)
from oscar_cs.paths import DATA_PROCESSED, ROOT

SQL_DIR = ROOT / "sql"
TIER_ORDER = ["none", "low", "med", "high"]


def one(con, query: str, params: dict | None = None) -> int:
    return int(con.execute(query, params or {}).fetchone()[0])


def build_claims_mapped(con) -> dict:
    """Create the claims_mapped temp table; return the counted exclusions."""
    window = {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END}
    counts = {
        "rows_total": one(con, "select count(*) from claim_lines"),
        "members_total": one(con, "select count(distinct member_id) from claim_lines"),
        "rows_null_date": one(
            con, "select count(*) from claim_lines where try_cast(date_svc as date) is null"
        ),
        "rows_pre_window": one(
            con,
            "select count(*) from claim_lines where try_cast(date_svc as date) < $ws",
            {"ws": window["ws"]},
        ),
        "rows_post_window": one(
            con,
            "select count(*) from claim_lines where try_cast(date_svc as date) > $we",
            {"we": window["we"]},
        ),
    }
    con.execute(
        f"create temp table claims_mapped as {read_sql(SQL_DIR / 'claims_clean_mapped.sql')}",
        {
            "window_start": ANALYSIS_WINDOW_START,
            "window_end": ANALYSIS_WINDOW_END,
            "symptoms_chapter": SYMPTOMS_CHAPTER,
            "residual_chapter": RESIDUAL_CHAPTER,
            "immunizations_level2": IMMUNIZATIONS_LEVEL2,
            "excluded_prefix": EXCLUDED_CODE_PREFIX,
        },
    )
    counts["rows_clean"] = one(con, "select count(*) from claims_mapped")
    counts["members_clean"] = one(con, "select count(distinct member_id) from claims_mapped")
    counts["members_lost_by_cleaning"] = counts["members_total"] - counts["members_clean"]
    return counts


def mapping_stats(con) -> dict:
    bucket_rows = dict(
        con.execute("select bucket, count(*) from claims_mapped group by bucket").fetchall()
    )
    bucket_members = dict(
        con.execute(
            "select bucket, count(distinct member_id) from claims_mapped group by bucket"
        ).fetchall()
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
    return {
        "bucket_rows": {k: int(v) for k, v in sorted(bucket_rows.items())},
        "bucket_members": {k: int(v) for k, v in sorted(bucket_members.items())},
        "row_map_coverage_pct": round(100 * mapped / rows_clean, 2),
        "unmapped_distinct_codes": unmapped_codes,
        "top_unmapped_codes": [(c, int(n)) for c, n in top_unmapped],
    }


def build_condition_tables(con) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Member x condition with capped shapes, member x symptom, and cap stats."""
    span_param = {"episode_max_span_days": EPISODE_MAX_SPAN_DAYS}
    conditions = con.execute(read_sql(SQL_DIR / "member_conditions.sql"), span_param).df()
    assert not (conditions["ccs_2_desc"].str.strip() == "").any(), (
        "blank level-2 desc outside the Residual chapter — policy assumption broken"
    )
    conditions["ccs2_id"] = parse_ccs2_code(conditions["ccs_2_desc"])
    conditions["condition"] = conditions["ccs_2_desc"].map(display_name)
    conditions["acute_only"] = [
        is_acute_only(chap, cond)
        for chap, cond in zip(conditions["chapter"], conditions["condition"], strict=True)
    ]
    capped = conditions["acute_only"] & (conditions["shape_raw"] == "chronic")
    conditions["shape"] = conditions["shape_raw"].where(~capped, "episode")

    symptoms = con.execute(read_sql(SQL_DIR / "member_symptoms.sql"), span_param).df()

    cap_stats = {
        "pairs_capped_chronic_to_episode": int(capped.sum()),
        "pct_of_acute_only_pairs_capped": round(
            100 * capped.sum() / max(conditions["acute_only"].sum(), 1), 2
        ),
        "top_capped_conditions": conditions.loc[capped, "condition"]
        .value_counts()
        .head(5)
        .to_dict(),
    }
    return conditions, symptoms, cap_stats


def build_member_summary(con, conditions: pd.DataFrame, symptoms: pd.DataFrame) -> pd.DataFrame:
    summary = con.execute(read_sql(SQL_DIR / "member_summary.sql")).df()
    int_cols = [
        "n_symptom_lines",
        "n_admin_lines",
        "n_immunization_lines",
        "n_residual_lines",
        "n_unmapped_lines",
    ]
    summary[int_cols] = summary[int_cols].astype(int)  # duckdb sum() arrives as float

    shape_counts = (
        conditions.pivot_table(
            index="member_id", columns="shape", values="condition", aggfunc="count"
        )
        .reindex(columns=["chronic", "episode", "one_off"])
        .fillna(0)
        .astype(int)
        .rename(columns=lambda s: f"n_{s}")
        .reset_index()
    )
    summary = summary.merge(shape_counts, on="member_id", how="left")
    shape_cols = ["n_chronic", "n_episode", "n_one_off"]
    summary[shape_cols] = summary[shape_cols].fillna(0).astype(int)
    summary["n_conditions"] = summary[shape_cols].sum(axis=1)

    persistent = symptoms.loc[symptoms["shape"] == "persistent", "member_id"].unique()
    summary["symptoms_persistent"] = summary["member_id"].isin(persistent)

    summary["profile_class"] = np.select(
        [
            summary["n_chronic"] > 0,
            summary["n_episode"] > 0,
            summary["n_one_off"] > 0,
            summary["n_symptom_lines"] > 0,
        ],
        ["chronic", "episodic", "one_off_only", "symptom_only"],
        default="admin_or_unmapped_only",
    )
    return summary


def build_tiers_and_contingency(con, summary: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Union population (claims or rx in window) with tiers, flags, and the 4x4 table."""
    rx = con.execute(
        """select member_id, count(*) as rx_fills from prescription_drugs
           where try_cast(date_svc as date) between $ws and $we group by member_id""",
        {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END},
    ).df()

    union = summary[["member_id", "n_lines"]].rename(columns={"n_lines": "dx_lines"})
    union = union.merge(rx, on="member_id", how="outer")
    union[["dx_lines", "rx_fills"]] = union[["dx_lines", "rx_fills"]].fillna(0).astype(int)

    dx_cut1, dx_cut2 = head_tail_cuts(union["dx_lines"])
    rx_cut1, rx_cut2 = head_tail_cuts(union["rx_fills"])
    union["dx_tier"] = assign_tier(union["dx_lines"], dx_cut1, dx_cut2)
    union["rx_tier"] = assign_tier(union["rx_fills"], rx_cut1, rx_cut2)

    dx_p99 = float(union.loc[union["dx_lines"] > 0, "dx_lines"].quantile(0.99))
    rx_p99 = float(union.loc[union["rx_fills"] > 0, "rx_fills"].quantile(0.99))
    union["dx_above_p99"] = union["dx_lines"] > dx_p99
    union["rx_above_p99"] = union["rx_fills"] > rx_p99
    union["high_utilizer"] = union["dx_above_p99"] & union["rx_above_p99"]

    observed = (
        union.pivot_table(
            index="dx_tier", columns="rx_tier", values="member_id", aggfunc="count", fill_value=0
        )
        .reindex(index=TIER_ORDER, columns=TIER_ORDER, fill_value=0)
        .astype(int)
    )
    n = observed.to_numpy().sum()
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / n
    lift = observed / expected

    tier_stats = {
        "population": {
            "union_members": int(len(union)),
            "claims_only": int(((union["dx_lines"] > 0) & (union["rx_fills"] == 0)).sum()),
            "rx_only": int(((union["dx_lines"] == 0) & (union["rx_fills"] > 0)).sum()),
            "both": int(((union["dx_lines"] > 0) & (union["rx_fills"] > 0)).sum()),
        },
        "cuts": {
            "dx": {"cut1": round(dx_cut1, 2), "cut2": round(dx_cut2, 2), "p99": dx_p99},
            "rx": {"cut1": round(rx_cut1, 2), "cut2": round(rx_cut2, 2), "p99": rx_p99},
        },
        "tier_sizes": {
            "dx": union["dx_tier"].value_counts().reindex(TIER_ORDER).astype(int).to_dict(),
            "rx": union["rx_tier"].value_counts().reindex(TIER_ORDER).astype(int).to_dict(),
        },
        "p99_flags": {
            "dx_above_p99": int(union["dx_above_p99"].sum()),
            "rx_above_p99": int(union["rx_above_p99"].sum()),
            "high_utilizer_both": int(union["high_utilizer"].sum()),
            "expected_both_if_independent": round(
                union["dx_above_p99"].mean() * union["rx_above_p99"].mean() * len(union), 1
            ),
        },
        "contingency_members": {
            r: {c: int(observed.loc[r, c]) for c in TIER_ORDER} for r in TIER_ORDER
        },
        "contingency_lift": {
            r: {c: round(float(lift.loc[r, c]), 2) for c in TIER_ORDER} for r in TIER_ORDER
        },
    }
    return union, tier_stats


def population_stats(
    conditions: pd.DataFrame, symptoms: pd.DataFrame, summary: pd.DataFrame
) -> dict:
    members = len(summary)  # denominator: members with >=1 kept in-window claim line
    shape_members = (
        conditions.pivot_table(
            index=["chapter", "condition"],
            columns="shape",
            values="member_id",
            aggfunc="nunique",
        )
        .reindex(columns=["chronic", "episode", "one_off"])
        .fillna(0)
        .astype(int)
    )
    shape_members["members_any"] = shape_members.sum(axis=1)
    prevalence = shape_members.reset_index().sort_values("members_any", ascending=False)
    prevalence["pct_members_any"] = (100 * prevalence["members_any"] / members).round(1)

    top_symptoms = (
        symptoms.groupby("symptom")["member_id"]
        .nunique()
        .sort_values(ascending=False)
        .head(10)
        .astype(int)
        .to_dict()
    )
    dist = summary["n_conditions"].value_counts().sort_index()
    return {
        "denominator": "members with >=1 kept in-window claim line",
        "members_characterized": members,
        "member_mix": summary["profile_class"].value_counts().to_dict(),
        "pct_members_chronic": round(100 * (summary["n_chronic"] > 0).mean(), 1),
        "conditions_per_member": {
            "mean": round(summary["n_conditions"].mean(), 2),
            "median": float(summary["n_conditions"].median()),
            "p90": float(summary["n_conditions"].quantile(0.9)),
            "max": int(summary["n_conditions"].max()),
            "distribution_head": {int(k): int(v) for k, v in dist.head(8).items()},
        },
        "top20_conditions_by_shape": prevalence.head(20).to_dict(orient="records"),
        "top10_symptoms_by_members": top_symptoms,
        "members_with_symptom_track": int((summary["n_symptom_lines"] > 0).sum()),
        "members_symptoms_persistent": int(summary["symptoms_persistent"].sum()),
    }


def pick_vignettes(
    conditions: pd.DataFrame, symptoms: pd.DataFrame, summary: pd.DataFrame
) -> list[dict]:
    """Three deterministic archetypes, masked labels (ids stay in the local json only)."""
    indexed = summary.set_index("member_id")

    def render(label: str, member_id: str) -> str:
        subset = conditions.loc[conditions["member_id"] == member_id]
        return render_vignette(label, subset, indexed.loc[member_id])

    picks: list[dict] = []
    # A — the brief's example shape: chronic cancer plus an injury episode, few extras
    cancer = set(
        conditions.loc[
            (conditions["chapter"] == "Neoplasms") & (conditions["shape"] == "chronic"),
            "member_id",
        ]
    )
    injury = set(conditions.loc[conditions["chapter"] == "Injury and poisoning", "member_id"])
    tidy = indexed[indexed["n_conditions"].between(2, 4)]
    a_pool = sorted((cancer & injury) & set(tidy.index))
    if a_pool:
        picks.append({"archetype": "A: cancer + injury", "member_id": a_pool[0]})
    # B — most multimorbid chronic member (exercises the +N more cap)
    b_id = summary.sort_values(["n_chronic", "member_id"], ascending=[False, True]).iloc[0][
        "member_id"
    ]
    picks.append({"archetype": "B: multimorbid chronic", "member_id": b_id})
    # C — persistent symptoms, no conditions: the new R-code track standing alone
    c_mask = (summary["n_conditions"] == 0) & summary["symptoms_persistent"]
    c_pool = summary.loc[c_mask].sort_values("n_symptom_days", ascending=False)
    if not c_pool.empty:
        picks.append(
            {"archetype": "C: persistent symptoms only", "member_id": c_pool.iloc[0]["member_id"]}
        )
    for pick in picks:
        pick["text"] = render(pick["archetype"][0], pick["member_id"])
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
            "window": [str(ANALYSIS_WINDOW_START), str(ANALYSIS_WINDOW_END)],
            "shape_rule": (
                f"one_off = 1 date; episode = >=2 dates, span <= {EPISODE_MAX_SPAN_DAYS}d; "
                f"chronic = span > {EPISODE_MAX_SPAN_DAYS}d (injuries/infections capped at episode)"
            ),
            "tier_rule": "head/tail breaks on positives; zero its own bin; flags above p99",
            "excluded_buckets": ["admin (Z-codes)", "immunizations", "residual", "unmapped"],
        }
    }
    stats["exclusions"] = build_claims_mapped(con)
    stats["mapping"] = mapping_stats(con)

    conditions, symptoms, cap_stats = build_condition_tables(con)
    stats["reinfection_cap"] = cap_stats
    summary = build_member_summary(con, conditions, symptoms)
    union, tier_stats = build_tiers_and_contingency(con, summary)
    stats["tiers"] = tier_stats
    stats["population"] = population_stats(conditions, symptoms, summary)

    summary = summary.merge(
        union[
            [
                "member_id",
                "rx_fills",
                "dx_tier",
                "rx_tier",
                "dx_above_p99",
                "rx_above_p99",
                "high_utilizer",
            ]
        ],
        on="member_id",
        how="left",
    )
    vignettes = pick_vignettes(conditions, symptoms, summary)
    stats["vignettes"] = vignettes

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    conditions.to_parquet(DATA_PROCESSED / "member_conditions.parquet", index=False)
    symptoms.to_parquet(DATA_PROCESSED / "member_symptoms.parquet", index=False)
    summary.to_parquet(DATA_PROCESSED / "member_health_status.parquet", index=False)
    union.to_parquet(DATA_PROCESSED / "member_tiers.parquet", index=False)
    with open(DATA_PROCESSED / "health_status_stats.json", "w") as fh:
        json.dump(stats, fh, indent=2, default=str)

    print(json.dumps({k: v for k, v in stats.items() if k != "vignettes"}, indent=2, default=str))
    print("\nVignettes (labels masked; raw ids only in the local stats json):")
    for pick in vignettes:
        print(f"  [{pick['archetype']}] {pick['text']}")
    print(
        f"\nWrote member_conditions ({len(conditions):,}), member_symptoms "
        f"({len(symptoms):,}), member_health_status ({len(summary):,}), "
        f"member_tiers ({len(union):,}) to {DATA_PROCESSED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
