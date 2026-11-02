"""Ablation: how much of the rx model is just "sick members fill more prescriptions"?

Refits every requirement-2 condition on the two utilization features alone
(log1p total fills, log1p distinct classes) with the same population, split and
estimator as scripts/build_rx_model.py, then compares test-set AUROC/AUPRC against
the full 671-feature model. A condition whose full model barely beats the
utilization-only one is being scored on volume, not pharmacology — the report must
not claim drug-specific signal for it.

Output: data/processed/utilization_ablation.json + a printed comparison table.
Usage: python scripts/check_utilization_baseline.py  (after build_rx_model.py)
"""

from __future__ import annotations

import json

import pandas as pd
from build_rx_model import SEED, load_labels, load_rx_features
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

from oscar_cs.db import connect_views
from oscar_cs.paths import DATA_PROCESSED


def main() -> int:
    con = connect_views()
    members, x, feature_names, _ = load_rx_features(con)
    labels, in_claims = load_labels(members)
    assert feature_names[-2:] == ["log1p_total_fills", "log1p_n_classes"]
    x_util = x[:, -2:].toarray()  # dense is fine: n x 2

    # identical split to build_rx_model.py (same seed, same member ordering)
    train_pop = members[in_claims].to_numpy()
    train_ids, test_ids = train_test_split(train_pop, test_size=0.2, random_state=SEED)
    train_mask = members.isin(set(train_ids))
    test_mask = members.isin(set(test_ids))

    with open(DATA_PROCESSED / "rx_model_metrics.json") as fh:
        full = {c["condition"]: c for c in json.load(fh)["metrics"]["conditions"]}

    rows = []
    for cond in labels.columns:
        y = labels[cond].to_numpy()
        model = LogisticRegression(max_iter=2000, C=1.0)
        model.fit(x_util[train_mask], y[train_mask])
        p = model.predict_proba(x_util[test_mask])[:, 1]
        y_test = y[test_mask]
        f = full[cond]
        rows.append(
            {
                "condition": cond,
                "auroc_full": f["auroc"],
                "auroc_util": round(float(roc_auc_score(y_test, p)), 3),
                "auprc_full": f["auprc"],
                "auprc_util": round(float(average_precision_score(y_test, p)), 3),
                "auprc_baseline": f["auprc_baseline"],
            }
        )
    out = pd.DataFrame(rows)
    out["auprc_ratio_full_vs_util"] = (out["auprc_full"] / out["auprc_util"]).round(1)
    out = out.sort_values("auprc_ratio_full_vs_util", ascending=False)

    with open(DATA_PROCESSED / "utilization_ablation.json", "w") as fh:
        json.dump(out.to_dict(orient="records"), fh, indent=2)
    with pd.option_context("display.width", 140, "display.max_colwidth", 48):
        print(out.to_string(index=False))
    print(
        "\nReading: auprc_ratio_full_vs_util = how many times the full model's AUPRC"
        " exceeds the utilization-only model's. Near 1 = the condition is scored on"
        " volume, not drug choice."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
