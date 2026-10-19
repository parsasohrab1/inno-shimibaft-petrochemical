"""Module 4 — Production Forecasting & Real-Time Operational Decision Support.

Implements docs/SRS.md section 3.1.4's acceptance criteria with real
models (``backend/app/ml/module4_forecast.py``):
  - FR-M4-01: a Holt's-smoothing 1-8h production-rate forecaster, RMSE%
    measured by rolling-origin backtesting — replacing the old flat
    historical-sum ``outlook``.
  - FR-M2-04/FR-M4-03: ``what_if`` now re-simulates through the trained
    module 2 (energy baseline) and module 3 (purity regressor) models
    with the perturbed parameter — not a scalar multiply — and
    ``rank_scenarios`` produces >= 3 multi-criteria-scored alternatives.
  - FR-M4-02/NFR-06: recommendations carry an explicit
    ``suggested_action``/``expected_effect`` payload computed from the
    real modules, and operator accept/reject is an APPEND-ONLY audit
    trail (``recommendation_decisions`` — see backend/app/db.py) —
    the original recommendation row is never mutated or deleted, the
    pattern used by the Khorasan Petrochemical SEM project's
    advisory-mode on this account.

Trained on synthetic data only — see backend/app/ml/__init__.py.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import numpy as np

from ..db import rows
from ..ml import module3_quality as m3
from ..ml import module4_forecast as m4
from ..ml import registry


def outlook(conn: sqlite3.Connection, horizon_hours: int = 8) -> dict:
    """FR-M4-01: a real 1-8h forecast, not a historical sum.

    Forecasts from the trained model's own recent synthetic reference
    series (``recent_production_series`` in the artifact bundle) rather
    than the seeded ``production_records`` table, because that table has
    too few/irregular points to serve as Holt's-smoothing state (see
    backend/app/seed.py) — this is stated plainly in the response.
    """
    if not registry.is_ready():
        return {"ready": False, "is_placeholder": False, "note": "مدل‌ها هنوز آموزش ندیده‌اند"}

    artifacts = registry.get_artifacts()
    model: m4.ForecastModel = artifacts["forecast_model"]
    recent_series = np.array(artifacts["recent_production_series"])

    forecasts = {}
    for h in (1, 2, 4, 8):
        if h > horizon_hours:
            continue
        forecasts[h] = m4.forecast_from_recent(model, recent_series, h)

    return {
        "ready": True,
        "is_placeholder": False,
        "data_source": "سری اخیر مرجع سنتتیک (backend/app/ml/synthetic.py) — نه داده لحظه‌ای واقعی کارخانه",
        "method": "هموارسازی نمایی خطی هولت (Holt's linear exponential smoothing), بازه‌بندی ۱۵ دقیقه‌ای",
        "forecast_kg_h_by_horizon_h": forecasts,
        "measured_rmse_pct_by_horizon_h": model.rmse_pct_by_horizon_h,
        "overall_rmse_pct": model.overall_rmse_pct,
        "target_rmse_pct": model.target_rmse_pct,
        "meets_target": model.meets_target,
    }


def what_if(conn: sqlite3.Connection, parameter: str, delta_pct: float, note: str | None) -> dict:
    """FR-M2-04 — a real re-simulation through modules 2 & 3's trained
    models, replacing the old linear-percentage placeholder.
    """
    if not registry.is_ready():
        return {"is_placeholder": False, "ready": False, "note": "مدل‌ها هنوز آموزش ندیده‌اند"}
    if parameter not in m4.WHATIF_PARAMETERS:
        return {
            "ready": True,
            "is_placeholder": False,
            "error": f"پارامتر ناشناخته: {parameter}",
            "valid_parameters": m4.WHATIF_PARAMETERS,
        }

    artifacts = registry.get_artifacts()
    result = m4.resimulate(
        artifacts["baseline_features"], artifacts["purity_regressor"], artifacts["energy_baseline"], parameter, delta_pct
    )
    return {
        "ready": True,
        "is_placeholder": False,
        "parameter": parameter,
        "delta_pct": delta_pct,
        "note": note,
        "baseline": result.baseline,
        "scenario": result.scenario,
        "method": "بازاجرای واقعی مدل خلوص (ماژول ۳) و خط پایه انرژی (ماژول ۲) با پارامتر تغییریافته — نه برآورد خطی",
    }


def rank_operating_scenarios(conn: sqlite3.Connection) -> dict:
    """FR-M4-03: >= 3 scenarios, each re-simulated, multi-criteria ranked."""
    if not registry.is_ready():
        return {"ready": False, "note": "مدل‌ها هنوز آموزش ندیده‌اند"}
    artifacts = registry.get_artifacts()
    ranked = m4.rank_scenarios(artifacts["baseline_features"], artifacts["purity_regressor"], artifacts["energy_baseline"])
    return {
        "ready": True,
        "weights_note": "امتیاز وزن‌دهی‌شده: تولید ۰.۴ + حاشیه کیفیت ۰.۳ + (۱ - شدت انرژی نرمال‌شده) ۰.۳",
        "scenarios": [
            {
                "name": s.name,
                "delta": s.delta,
                "production_rate_kg_h": s.production_rate_kg_h,
                "predicted_purity_pct": s.predicted_purity_pct,
                "predicted_energy_intensity_gj_per_t": s.predicted_energy_intensity_gj_per_t,
                "score": s.score,
            }
            for s in ranked
        ],
        "recommended": ranked[0].name if ranked else None,
    }


# --- FR-M4-02 / NFR-06: recommendations + append-only audit trail ---------


def list_recommendations(conn: sqlite3.Connection) -> list[dict]:
    recs = [dict(r) for r in rows(conn, "SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 50")]
    for r in recs:
        r["suggested_action"] = json.loads(r["suggested_action"]) if r.get("suggested_action") else None
        r["expected_effect"] = json.loads(r["expected_effect"]) if r.get("expected_effect") else None
        decisions = rows(
            conn, "SELECT decision, actor_username, note, ts FROM recommendation_decisions WHERE rec_id=? ORDER BY ts",
            (r["id"],),
        )
        r["decisions"] = [dict(d) for d in decisions]
        r["effective_status"] = decisions[-1]["decision"] if decisions else r["status"]
    return recs


def add_recommendation(
    conn: sqlite3.Connection,
    module: str,
    title: str,
    detail: str,
    impact: str,
    confidence: float,
    suggested_action: dict | None = None,
    expected_effect: dict | None = None,
) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO recommendations(module, title, detail, impact, confidence, suggested_action, expected_effect, "
        "status, created_at, is_sample) VALUES (?,?,?,?,?,?,?, 'pending', ?, 1)",
        (
            module,
            title,
            detail,
            impact,
            confidence,
            json.dumps(suggested_action, ensure_ascii=False) if suggested_action else None,
            json.dumps(expected_effect, ensure_ascii=False) if expected_effect else None,
            now,
        ),
    )
    conn.commit()
    return cur.lastrowid


def record_decision(conn: sqlite3.Connection, rec_id: int, decision: str, actor_username: str | None, note: str | None) -> None:
    """NFR-06 — append-only: a new audit row per accept/reject, the
    original ``recommendations`` row is never UPDATEd or DELETEd.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO recommendation_decisions(rec_id, decision, actor_username, note, ts) VALUES (?,?,?,?,?)",
        (rec_id, decision, actor_username, note, now),
    )
    conn.commit()


def auto_recommend_from_quality(conn: sqlite3.Connection, actor_username: str | None = None) -> dict | None:
    """Generate one recommendation from the real module-3 OOS estimate,
    with a suggested_action + expected_effect computed via module 4's
    re-simulation (FR-M4-02's two-part structure, wired to real outputs —
    not free text).

    Returns None if the models are not trained or the current estimate
    does not warrant a recommendation (purity comfortably in spec).
    """
    if not registry.is_ready():
        return None
    artifacts = registry.get_artifacts()
    baseline_features = artifacts["baseline_features"]
    reg: m3.PurityRegressionResult = artifacts["purity_regressor"]
    energy_baseline = artifacts["energy_baseline"]

    current_purity = m3.predict_purity(reg, baseline_features)
    margin = current_purity - 97.0  # MTBE_PURITY_SPEC_MIN
    if margin > 1.0:
        return None  # comfortably in spec, nothing to recommend

    # move the feed ratio toward its physical optimum (1.1) as the action
    ratio = baseline_features["meoh_isobutene_ratio"]
    delta_pct = (1.1 - ratio) / ratio * 100.0
    resim = m4.resimulate(baseline_features, reg, energy_baseline, "meoh_isobutene_ratio", delta_pct)

    suggested_action = {"parameter": "meoh_isobutene_ratio", "delta_pct": round(delta_pct, 2)}
    expected_effect = {
        "purity_delta_pct": round(resim.scenario["predicted_purity_pct"] - resim.baseline["predicted_purity_pct"], 3),
        "production_delta_kg_h": round(
            resim.scenario["production_rate_kg_h"] - resim.baseline["production_rate_kg_h"], 1
        ),
        "energy_intensity_delta_gj_per_t": round(
            resim.scenario["predicted_energy_intensity_gj_per_t"]
            - resim.baseline["predicted_energy_intensity_gj_per_t"],
            4,
        ),
    }
    rec_id = add_recommendation(
        conn,
        module="quality_prediction",
        title="تنظیم نسبت خوراک متانول:ایزوبوتیلن به سمت نقطه بهینه",
        detail=f"حاشیه خلوص برآوردی فعلی نسبت به حد پایین مشخصه ({margin:.2f}٪) کم است؛ "
        f"تغییر نسبت خوراک {delta_pct:+.1f}٪ به سمت ۱.۱ پیشنهاد می‌شود.",
        impact="quality",
        confidence=0.6,
        suggested_action=suggested_action,
        expected_effect=expected_effect,
    )
    return {"id": rec_id, "suggested_action": suggested_action, "expected_effect": expected_effect}
