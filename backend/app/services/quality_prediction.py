"""Module 3 — Smart Quality Prediction & Off-Spec Detection.

Implements (as heuristic placeholders — see TODOs) the acceptance criteria
of docs/SRS.md section 3.1.3:
  - FR-M3-01: MTBE purity prediction model (target purity >= 98%, MAE <= 0.3%);
  - FR-M3-02: predict OOS (out-of-spec) probability >= 30 minutes ahead
    (target True Positive Rate >= 85% on a validation set);
  - FR-M3-03: rank >= 3 contributing factors behind a quality deviation
    (e.g. reactor temperature TI-101, feed ratio FI-103/FI-104, catalyst
    activity).

This scaffold does NOT train a predictive model and does NOT satisfy any
of the above criteria. It only checks the seeded ``lab_samples`` rows
against their declared spec limits and reports a naive "distance from
spec" ratio as a stand-in risk score — there is no MAE to measure, no
30-minutes-ahead prediction (it only looks at the latest lab result, which
in reality lags by up to 24h per SRS 2.3), and no real TPR, since nothing
is actually predicted ahead of time.

TODO (real implementation, needs real paired process + lab history):
  - a trained regression model per product/parameter (e.g. PLS, gradient
    boosting) using process tag windows as features, measured against
    FR-M3-01's MAE <= 0.3% target;
  - a genuine 30-minute-ahead OOS classifier with a measured TPR, to
    satisfy FR-M3-02 — this scaffold has no forward-looking logic at all;
  - contributing-factor attribution (e.g. SHAP or similar, per AI-04 in
    docs/SRS.md) tied to real process tags, not the fixed placeholder
    string ``_placeholder_factors`` returns today.
"""
from __future__ import annotations

import sqlite3

from ..db import rows


def offspec_risk(conn: sqlite3.Connection) -> list[dict]:
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
            "contributing_factors": _placeholder_factors(r["product"], r["parameter"]),
        })
    return sorted(items, key=lambda x: x["offspec_risk_0_1"], reverse=True)


def _placeholder_factors(product: str, parameter: str) -> list[str]:
    """Fixed illustrative text — NOT model-derived attribution.

    Real contributing-factor identification needs a trained model over
    real process + lab history (see module docstring above).
    """
    return [
        "جای‌نگه‌دار: عامل مؤثر واقعی باید از مدل آموزش‌دیده روی داده فرآیند و آزمایشگاه واقعی استخراج شود",
    ]
