"""Module 3 — Smart Quality Prediction & Off-Spec Detection.

Implements docs/SRS.md section 3.1.3's acceptance criteria with real
trained models (``backend/app/ml/module3_quality.py``):
  - FR-M3-01: a GradientBoostingRegressor predicting MTBE purity from
    DCS-only process-tag features, MAE measured on a held-out test split.
  - FR-M3-02: a GradientBoostingClassifier predicting whether purity will
    be below spec 30 minutes ahead, TPR/precision/AUC measured on a
    held-out test split (see module3_quality.train_oos_classifier's
    docstring for the split-methodology caveat and the honestly-low
    precision at the target recall level).
  - FR-M3-03: real feature-importance ranking from the trained
    regressor, mapped to tag IDs — not a fixed placeholder string.

The seeded ``lab_samples`` table (illustrative, random, is_sample=1) is
still used for the "latest lab result vs spec" table the UI showed
before; ``model_predictions`` below is the new, real, DCS-feature-driven
prediction, and is what actually satisfies FR-M3-01/02/03. Both are
returned so the UI can show the (honest) difference between a
last-known-lab-result view and the model's real-time estimate.

Trained on synthetic data only — see backend/app/ml/__init__.py.
"""
from __future__ import annotations

import sqlite3

from ..db import rows
from ..ml import module3_quality as m3
from ..ml import registry
from ..ml.synthetic import PROCESS_FEATURE_COLUMNS, TAG_TO_SYNTHETIC_COLUMN


def offspec_risk(conn: sqlite3.Connection) -> list[dict]:
    """Unchanged simple "distance from spec" view of the seeded lab
    samples — kept because it is an honest, simple summary of sample lab
    data, which the model_predictions() below does not replace (lab
    results and model estimates answer different questions).
    """
    items = []
    for r in rows(conn, "SELECT * FROM lab_samples ORDER BY sampled_at DESC LIMIT 30"):
        lo, hi, val = r["spec_min"], r["spec_max"], r["value"]
        if lo is None or hi is None:
            continue
        span = (hi - lo) or 1.0
        if val < lo:
            risk = min(1.0, (lo - val) / span)
        elif val > hi:
            risk = min(1.0, (val - hi) / span)
        else:
            margin = min(val - lo, hi - val)
            risk = max(0.0, 0.3 - margin / span)  # close to an edge but inside spec
        items.append({
            "sample_id": r["sample_id"],
            "product": r["product"],
            "parameter": r["parameter"],
            "value": val,
            "spec_min": lo,
            "spec_max": hi,
            "offspec_risk_0_1": round(risk, 3),
            "contributing_factors": _factors_for(r["product"], r["parameter"]),
        })
    return sorted(items, key=lambda x: x["offspec_risk_0_1"], reverse=True)


def _factors_for(product: str, parameter: str) -> list[dict]:
    """FR-M3-03 — real feature-importance ranking, not a fixed string,
    for the one product/parameter combination the trained model covers
    (MTBE purity_pct). Everything else honestly says it is not modelled.
    """
    if product == "MTBE" and parameter == "purity_pct" and registry.is_ready():
        reg: m3.PurityRegressionResult = registry.get_artifacts()["purity_regressor"]
        return reg.feature_importance_ranking()[:3]
    return [{"feature": None, "tag_label": "مدل‌سازی نشده برای این محصول/پارامتر", "importance": None}]


def model_predictions(conn: sqlite3.Connection) -> dict:
    """FR-M3-01/02/03 live view: feed the latest DCS tag readings (the
    seeded ``historian_samples`` ticker, labelled as sample data) through
    the trained purity regressor and OOS classifier.
    """
    if not registry.is_ready():
        return {"ready": False, "note": "مدل‌ها هنوز آموزش ندیده‌اند"}

    artifacts = registry.get_artifacts()
    reg: m3.PurityRegressionResult = artifacts["purity_regressor"]
    clf: m3.OosClassifierResult = artifacts["oos_classifier"]
    baseline_features: dict = artifacts["baseline_features"]

    # latest live-ish reading per modelled column, falling back to the
    # trained reference mean when the seeded ticker has nothing yet
    latest: dict[str, float] = dict(baseline_features)
    reverse_map = {v: k for k, v in TAG_TO_SYNTHETIC_COLUMN.items()}
    for column in PROCESS_FEATURE_COLUMNS:
        tag_id = reverse_map.get(column)
        if not tag_id:
            continue
        sample = rows(conn, "SELECT value FROM historian_samples WHERE tag_id=? ORDER BY ts DESC LIMIT 1", (tag_id,))
        if sample:
            latest[column] = sample[0]["value"]

    purity = m3.predict_purity(reg, latest)

    # the classifier also needs the rolling-window features — not
    # available from a single seeded sample point, so approximate with
    # zero trend/spread (i.e. "assume currently flat", clearly labelled)
    clf_features = dict.fromkeys(clf.features, 0.0)
    for c in PROCESS_FEATURE_COLUMNS:
        clf_features[c] = latest.get(c, baseline_features.get(c, 0.0))
    oos_proba = m3.predict_oos_probability(clf, clf_features)

    return {
        "ready": True,
        "data_source": "ویژگی‌های فرآیندی زنده نمونه (historian_samples) از مدل آموزش‌دیده روی داده سنتتیک",
        "input_features": {k: round(v, 4) for k, v in latest.items() if k in PROCESS_FEATURE_COLUMNS},
        "predicted_purity_pct": round(purity, 3),
        "purity_model": {
            "mae_test_pct": reg.mae_test_pct,
            "target_mae_pct": reg.target_mae_pct,
            "meets_target": reg.meets_target,
        },
        "oos_30min_probability": round(oos_proba, 4),
        "oos_30min_flag": oos_proba >= clf.decision_threshold,
        "oos_model": {
            "decision_threshold": clf.decision_threshold,
            "tpr_test": clf.tpr_test,
            "precision_test": clf.precision_test,
            "auc_test": clf.auc_test,
            "target_tpr": clf.target_tpr,
            "meets_target": clf.meets_target,
            "caveat": "رویکرد ارزیابی در Docstring backend/app/ml/module3_quality.py توضیح داده شده — دقت (precision) پایین است",
        },
        "contributing_factors": reg.feature_importance_ranking(),
        "note_oos_features": "ویژگی‌های روند/پراکندگی ۱۰ دقیقه برای این نمای تک‌نمونه‌ای صفر فرض شده (داده تاریخچه کافی موجود نیست)",
    }
