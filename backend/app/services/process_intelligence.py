"""Module 1 — Process Intelligence & Operating-Condition Optimization.

Implements docs/SRS.md section 3.1.1's measurable acceptance criteria for
real, not fixed-band-heuristic, analysis:
  - FR-M1-02: a data-driven operating envelope + a genuine 95% CI per key
    tag — ``backend/app/ml/module1_process.py``'s ``compute_operating_envelopes``,
    trained on the synthetic generator (no real Historian — see
    ``services/dcs_ingest.py``, still ``NotImplementedError``, for
    FR-M1-01, which genuinely needs one).
  - FR-M1-03: multivariate correlation of 5 process variables against a
    productivity-proxy KPI, with a measured R^2 — see
    ``backend/app/ml/module1_process.train_productivity_correlation`` and
    its docstring's honesty caveat about the engineered KPI.

Only 5 of the 10 seeded tags (TI-101, PI-102, FI-103, FI-301, EI-401) are
covered by the synthetic generator and therefore have a real envelope;
the rest (FI-104, AI-105, TI-201, and the MEK placeholders TI-501/TI-502)
fall back to the old fixed-band heuristic, now explicitly labelled
``not_modeled`` rather than presented as equivalent.

Everything here is trained on synthetic data only — see
``backend/app/ml/__init__.py``. Results are measured on a synthetic
validation set, not on real plant data.
"""
from __future__ import annotations

import sqlite3
import statistics

from ..db import rows
from ..ml import registry
from ..ml.synthetic import TAG_TO_SYNTHETIC_COLUMN


def list_tags(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in rows(conn, "SELECT * FROM process_tags ORDER BY unit, tag_id")]


def _status_from_band(value: float, lo: float, hi: float) -> tuple[str, str]:
    span = (hi - lo) or 1.0
    margin = span * 0.1
    if value < lo - margin or value > hi + margin:
        return "red", "خارج از محدوده مجاز"
    if value < lo or value > hi:
        return "yellow", "نزدیک به مرز محدوده"
    return "green", "درون محدوده نرمال"


def tag_envelope(conn: sqlite3.Connection, tag_id: str) -> dict | None:
    """Exact value + range + a red/yellow/green status with a text label
    (never colour alone — the convention used on the Khorasan Petrochemical
    SEM dashboard on this account, kept here for consistency).

    For the 5 tags the synthetic generator models (TAG_TO_SYNTHETIC_COLUMN),
    the comparison band is the trained model's data-driven
    ``operating_band_p2_5_97_5`` (FR-M1-02), not the old fixed seed row —
    the response also carries the 95% CI on the mean and says plainly this
    is measured on synthetic data. For everything else, the original
    fixed-band heuristic is kept, now labelled ``not_modeled``.
    """
    tag = rows(conn, "SELECT * FROM process_tags WHERE tag_id=?", (tag_id,))
    if not tag:
        return None
    tag = dict(tag[0])
    samples = rows(conn, "SELECT value, ts FROM historian_samples WHERE tag_id=? ORDER BY ts DESC LIMIT 1", (tag_id,))
    if not samples:
        return {**tag, "value": None, "ts": None, "status": "unknown", "status_label": "بدون داده"}
    value, ts = samples[0]["value"], samples[0]["ts"]

    if tag_id in TAG_TO_SYNTHETIC_COLUMN and registry.is_ready():
        try:
            envelope = registry.get_artifacts()["envelopes"][tag_id]
        except (registry.ModelsNotTrained, KeyError):
            envelope = None
        if envelope is not None:
            lo, hi = envelope.operating_band_p2_5_97_5
            status, label = _status_from_band(value, lo, hi)
            return {
                **tag,
                "value": value,
                "ts": ts,
                "status": status,
                "status_label": label,
                "basis": "model",
                "operating_band_p2_5_97_5": [lo, hi],
                "ci95_of_mean": list(envelope.ci95_of_mean),
                "model_mean": envelope.mean,
                "model_std": envelope.std,
                "model_n": envelope.n,
                "note": "محدوده و بازه اطمینان ۹۵٪ از مدل آموزش‌دیده روی داده سنتتیک — نه داده واقعی کارخانه",
            }

    lo, hi = tag["normal_min"], tag["normal_max"]
    status, label = _status_from_band(value, lo, hi)
    return {
        **tag,
        "value": value,
        "ts": ts,
        "status": status,
        "status_label": label,
        "basis": "not_modeled",
        "note": "این تگ در مدل سنتتیک مدل‌سازی نشده — مقایسه با محدوده ثابت seed‌شده (جای‌نگه‌دار)",
    }


def variability_flags(conn: sqlite3.Connection) -> list[dict]:
    """Flag tags whose recent sample standard deviation looks unusually wide
    relative to their declared normal band — a crude stand-in for the
    letter's "conditions that increase variability or hurt stability".

    Kept as a simple live-data heuristic deliberately: it operates on the
    seeded/illustrative ``historian_samples`` ticker, which has no real
    temporal structure to fit a model to (see backend/app/seed.py) — the
    genuine statistical modelling for FR-M1-02/03 is in
    ``operating_envelope``/``productivity_correlation`` below, trained on
    the synthetic generator instead.
    """
    flags = []
    for tag in list_tags(conn):
        vals = [r["value"] for r in rows(
            conn, "SELECT value FROM historian_samples WHERE tag_id=? ORDER BY ts DESC LIMIT 30", (tag["tag_id"],)
        )]
        if len(vals) < 5:
            continue
        band = (tag["normal_max"] - tag["normal_min"]) or 1.0
        rel_stdev = statistics.pstdev(vals) / band
        if rel_stdev > 0.25:
            flags.append({
                "tag_id": tag["tag_id"],
                "unit": tag["unit"],
                "relative_variability": round(rel_stdev, 3),
                "note": "نوسان نسبی بالا نسبت به محدوده نرمال تعریف‌شده (آستانه ساده روی داده نمونه زنده، نه مدل آموزش‌دیده)",
            })
    return flags


def operating_envelopes() -> dict:
    """FR-M1-02: the trained data-driven envelope + 95% CI for every tag
    the synthetic generator models, as a flat dict keyed by tag_id.
    """
    if not registry.is_ready():
        return {"ready": False, "note": "مدل‌ها هنوز آموزش ندیده‌اند"}
    envelopes = registry.get_artifacts()["envelopes"]
    return {
        "ready": True,
        "data_source": "synthetic (backend/app/ml/synthetic.py) — not real plant data",
        "tags": {
            tag_id: {
                "column": env.column,
                "n": env.n,
                "mean": env.mean,
                "std": env.std,
                "ci95_of_mean": list(env.ci95_of_mean),
                "operating_band_p2_5_97_5": list(env.operating_band_p2_5_97_5),
            }
            for tag_id, env in envelopes.items()
        },
    }


def productivity_correlation() -> dict:
    """FR-M1-03: measured multivariate R^2 against the productivity proxy."""
    if not registry.is_ready():
        return {"ready": False, "note": "مدل‌ها هنوز آموزش ندیده‌اند"}
    corr = registry.get_artifacts()["correlation"]
    return {
        "ready": True,
        "target": corr.target,
        "target_note": (
            "FI-301 (دبی محصول MTBE) در مولد سنتتیک مستقیماً وجود ندارد؛ این یک شاخص مهندسی‌شده "
            "(feed_flow_kg_h × خلوص/۱۰۰) است، نه تگ اندازه‌گیری‌شده — رجوع کنید به Docstring ماژول"
        ),
        "features": corr.features,
        "coefficients": corr.coefficients,
        "intercept": corr.intercept,
        "r2_train": corr.r2_train,
        "r2_test": corr.r2_test,
        "n_train": corr.n_train,
        "n_test": corr.n_test,
        "target_r2": 0.7,
        "meets_target": corr.meets_target,
        "feature_count": len(corr.features),
        "meets_feature_count_target": len(corr.features) >= 5,
    }
