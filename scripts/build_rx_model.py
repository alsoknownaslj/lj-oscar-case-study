"""Requirement 2 — infer health status from prescription drug data alone.

Setup (guardrails: CLAUDE.md mistakes 4-6 and 8):
- Labels: per-member chronic flags for the 15 most prevalent chronic conditions, taken
  from the v2 characterization (claims/CCS only — rx never touches a label).
- Features: in-window rx only — log1p fill counts per drug_class (the 687-value level of
  the provided hierarchy), plus log1p total fills and distinct classes. Nothing from
  claims can leak in: every column derives from prescription_drugs.
- Population: members with >=1 in-window fill AND >=1 kept claim line (labels need
  claims; an rx-only model sees nothing for a member with zero fills). Same-period
  inference: features and labels share the canonical window — this predicts current
  status from current drug data, not future status.
- Model: one L2 logistic regression per condition (one-vs-rest — members carry several
  conditions at once). 80/20 split BY MEMBER, never by row. Metrics: AUROC and AUPRC
  per condition against the prevalence baseline (positives are rare, so accuracy says
  nothing). Scoring: the 37,583 in-window rx-only members get predicted probabilities.

Outputs (local-only, data/ is gitignored):
  data/processed/rx_model_metrics.json
  data/processed/rx_only_scores.parquet
Figures: reports/figures/2026-11-02_final_fig03/fig04 (via apply_theme in
scripts/report_figures.py).

Usage: python scripts/build_rx_model.py  (after build_health_status.py)
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

from oscar_cs.db import connect_views
from oscar_cs.health_status import ANALYSIS_WINDOW_END, ANALYSIS_WINDOW_START
from oscar_cs.paths import DATA_PROCESSED, FIGURES

N_CONDITIONS = 15
SEED = 42
STEM = "2026-11-02_final"
CALIBRATION_PICKS = [
    "Diabetes mellitus without complication",
    "Hypertension",
    "Diseases of the heart",
]


def load_rx_features(con) -> tuple[pd.Index, sparse.csr_matrix, list[str], pd.DataFrame]:
    """Per-member drug_class fill counts (sparse) + totals, in-window rx only."""
    fills = con.execute(
        """select member_id, drug_class, count(*) as n_fills
           from prescription_drugs
           where try_cast(date_svc as date) between $ws and $we
           group by member_id, drug_class""",
        {"ws": ANALYSIS_WINDOW_START, "we": ANALYSIS_WINDOW_END},
    ).df()
    members = pd.Index(sorted(fills["member_id"].unique()), name="member_id")
    classes = sorted(fills["drug_class"].unique())
    row = members.get_indexer(fills["member_id"])
    col = pd.Index(classes).get_indexer(fills["drug_class"])
    counts = sparse.csr_matrix(
        (fills["n_fills"].to_numpy(dtype="float64"), (row, col)),
        shape=(len(members), len(classes)),
    )
    totals = pd.DataFrame(
        {
            "total_fills": counts.sum(axis=1).A1,
            "n_classes": (counts > 0).sum(axis=1).A1,
        },
        index=members,
    )
    x = sparse.hstack(
        [counts.log1p(), np.log1p(totals[["total_fills", "n_classes"]].to_numpy())],
        format="csr",
    )
    feature_names = classes + ["log1p_total_fills", "log1p_n_classes"]
    return members, x, feature_names, totals


def load_labels(members: pd.Index) -> tuple[pd.DataFrame, pd.Series]:
    """Chronic flags from the v2 characterization for the top-N chronic conditions."""
    conditions = pd.read_parquet(DATA_PROCESSED / "member_conditions.parquet")
    chronic = conditions.loc[conditions["shape"] == "chronic", ["member_id", "condition"]]
    claims_members = pd.read_parquet(
        DATA_PROCESSED / "member_health_status.parquet", columns=["member_id"]
    )["member_id"]
    in_claims = members.isin(set(claims_members))

    eligible = chronic[chronic["member_id"].isin(members[in_claims])]
    top = eligible["condition"].value_counts().head(N_CONDITIONS)
    labels = pd.DataFrame(False, index=members, columns=top.index.tolist())
    for cond in top.index:
        has = set(eligible.loc[eligible["condition"] == cond, "member_id"])
        labels[cond] = members.isin(has)
    return labels, pd.Series(in_claims, index=members, name="in_claims")


def fit_and_score(
    x: sparse.csr_matrix,
    labels: pd.DataFrame,
    members: pd.Index,
    in_claims: pd.Series,
    feature_names: list[str],
) -> tuple[dict, pd.DataFrame, dict]:
    """Per-condition logistic regressions; metrics on the member-held-out 20%."""
    train_pop = members[in_claims].to_numpy()  # pandas-3 arrow index trips sklearn indexing
    train_ids, test_ids = train_test_split(train_pop, test_size=0.2, random_state=SEED)
    train_mask = members.isin(set(train_ids))
    test_mask = members.isin(set(test_ids))
    rx_only_mask = ~in_claims.to_numpy()

    metrics: dict = {
        "population": {
            "modeled_members": int(in_claims.sum()),
            "train_members": int(train_mask.sum()),
            "test_members": int(test_mask.sum()),
            "rx_only_scored": int(rx_only_mask.sum()),
        },
        "conditions": [],
    }
    scores = pd.DataFrame(index=members[rx_only_mask])
    calibration: dict = {}
    for cond in labels.columns:
        y = labels[cond].to_numpy()
        model = LogisticRegression(max_iter=2000, C=1.0)
        model.fit(x[train_mask.nonzero()[0]], y[train_mask])
        p_test = model.predict_proba(x[test_mask.nonzero()[0]])[:, 1]
        y_test = y[test_mask]
        prevalence = float(y_test.mean())
        top_idx = np.argsort(model.coef_[0])[::-1][:5]
        metrics["conditions"].append(
            {
                "condition": cond,
                "train_positives": int(y[train_mask].sum()),
                "test_prevalence_pct": round(100 * prevalence, 2),
                "auroc": round(float(roc_auc_score(y_test, p_test)), 3),
                "auprc": round(float(average_precision_score(y_test, p_test)), 3),
                "auprc_baseline": round(prevalence, 4),
                "top_positive_classes": [feature_names[i] for i in top_idx],
            }
        )
        scores[cond] = model.predict_proba(x[rx_only_mask])[:, 1]
        if cond in CALIBRATION_PICKS:
            frac_pos, mean_pred = calibration_curve(y_test, p_test, n_bins=10, strategy="quantile")
            calibration[cond] = {
                "mean_predicted": [round(float(v), 4) for v in mean_pred],
                "fraction_positive": [round(float(v), 4) for v in frac_pos],
            }
    return metrics, scores, calibration


def render_figures(metrics: dict, calibration: dict) -> None:
    import matplotlib.pyplot as plt
    from report_figures import BLUE, GRAY, INK_2, MUTED, ORANGE, apply_theme

    apply_theme()
    rows = pd.DataFrame(metrics["conditions"]).sort_values("auprc")

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 6.2), sharey=True)
    labels_short = [c[:38] + "…" if len(c) > 38 else c for c in rows["condition"]]
    axes[0].barh(labels_short, rows["auroc"], color=BLUE)
    axes[0].axvline(0.5, color=MUTED, ls="--", lw=1, label="chance (0.5)")
    axes[0].set_xlim(0, 1)
    axes[0].set_title("AUROC (test members)", loc="left")
    axes[0].legend(frameon=False, loc="lower right")
    axes[1].barh(labels_short, rows["auprc"], color=ORANGE, label="model AUPRC")
    axes[1].barh(
        labels_short, rows["auprc_baseline"], color=GRAY, height=0.35, label="prevalence baseline"
    )
    axes[1].set_xlim(0, 1)
    axes[1].set_title("AUPRC vs prevalence baseline", loc="left")
    axes[1].legend(frameon=False, loc="lower right")
    for ax in axes:
        ax.tick_params(axis="y", labelsize=9)
    fig.suptitle("Rx-only chronic-condition models, member-held-out test set", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIGURES / f"{STEM}_fig03_rx_model_metrics.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    ax.plot([0, 1], [0, 1], color=MUTED, ls="--", lw=1, label="perfect calibration")
    for (cond, curve), color in zip(calibration.items(), [BLUE, ORANGE, "#1baf7a"], strict=False):
        ax.plot(
            curve["mean_predicted"],
            curve["fraction_positive"],
            marker="o",
            ms=4,
            color=color,
            label=cond[:34],
        )
    lim = 1.05 * max(
        (max(c["mean_predicted"] + c["fraction_positive"]) for c in calibration.values()),
        default=1,
    )
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("mean predicted probability (quantile bins)")
    ax.set_ylabel("observed chronic share", color=INK_2)
    ax.set_title("Calibration, three exemplar conditions", loc="left", pad=12)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{STEM}_fig04_calibration.png")
    plt.close(fig)


def main() -> int:
    con = connect_views()
    members, x, feature_names, _ = load_rx_features(con)
    labels, in_claims = load_labels(members)
    metrics, scores, calibration = fit_and_score(x, labels, members, in_claims, feature_names)
    metrics["feature_space"] = {
        "n_features": x.shape[1],
        "drug_classes": x.shape[1] - 2,
        "note": "log1p fill counts per drug_class + log1p totals; rx-derived only",
    }

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    scores.reset_index().to_parquet(DATA_PROCESSED / "rx_only_scores.parquet", index=False)
    with open(DATA_PROCESSED / "rx_model_metrics.json", "w") as fh:
        json.dump({"metrics": metrics, "calibration": calibration}, fh, indent=2)
    render_figures(metrics, calibration)

    print(json.dumps(metrics, indent=2))
    print(f"\nWrote rx_only_scores ({len(scores):,} members) and metrics to {DATA_PROCESSED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
