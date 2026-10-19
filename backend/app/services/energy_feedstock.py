"""Module 2 — Smart Energy & Feedstock Optimization.

Implements docs/SRS.md section 3.1.2's acceptance criteria:
  - FR-M2-01/02: an ISO 50001-style Energy Baseline (EnB) regression,
    EnPI, CUSUM, and a deviation-detection rule whose recall is actually
    MEASURED against synthetically-injected deviations of known size
    (see ``backend/app/ml/module2_energy.py`` — the Khorasan Petrochemical
    SEM project's ``energy_perf.py`` pattern on this account), replacing
    the old flat sample-average/1.2x-threshold placeholder.
  - FR-M2-03: a real LP production-mix optimizer
    (``scipy.optimize.linprog``) over feedstock availability and product
    economics, producing >= 3 costed scenarios — replacing the old
    "highest-tonnage product" stub.
  - FR-M2-04: the actual what-if re-simulation now lives in
    ``services/forecasting_decision.py`` (it needs modules 2 AND 3's
    trained models, so it is wired there) — see that module.

Everything is trained on synthetic data only; see
``backend/app/ml/__init__.py``.
"""
from __future__ import annotations

import sqlite3
import statistics

from ..db import rows
from ..ml import module2_energy as m2
from ..ml import registry


def energy_intensity(conn: sqlite3.Connection) -> dict:
    """Simple descriptive stats on the seeded/illustrative production
    records (kept for the UI's "live sample data" table) PLUS the trained
    EnB model's parameters and its measured deviation-detection rate.

    The seeded ``production_records`` rows have no fixed, model-matching
    sampling interval (see backend/app/seed.py), so they are NOT run
    through the EnB regression directly — that would silently conflate
    two different time bases (the real bug caught and documented in
    module2_energy.predict_energy_gj). The EnB's own validated behaviour
    is reported separately, from its own training-time synthetic series.
    """
    recs = rows(conn, "SELECT product, quantity_t, energy_gj, ts FROM production_records ORDER BY ts DESC LIMIT 60")
    items = []
    intensities = []
    for r in recs:
        if r["quantity_t"]:
            gj_per_t = r["energy_gj"] / r["quantity_t"]
            intensities.append(gj_per_t)
            items.append({"product": r["product"], "ts": r["ts"], "gj_per_t": round(gj_per_t, 2)})
    avg = statistics.mean(intensities) if intensities else None
    flagged = [i for i in items if avg and i["gj_per_t"] > avg * 1.2]

    out = {
        "items": items,
        "average_gj_per_t": round(avg, 2) if avg else None,
        "flagged": flagged,
        "note": (
            "جدول بالا: میانگین ساده روی داده نمونه نمایشی (برچسب sample)، نه خط پایه رگرسیونی. "
            "پارامترهای EnB واقعی و نرخ تشخیص انحراف اندازه‌گیری‌شده را در energy_baseline ببینید."
        ),
    }
    if registry.is_ready():
        artifacts = registry.get_artifacts()
        baseline: m2.EnergyBaseline = artifacts["energy_baseline"]
        deviation = m2.evaluate_deviation_detection(baseline, _training_frame_cached())
        out["energy_baseline"] = {
            "ready": True,
            "data_source": "synthetic (backend/app/ml/synthetic.py) — not real plant data",
            "intercept_gj": baseline.intercept,
            "slope_gj_per_t": baseline.slope_gj_per_t,
            "interval_min": baseline.interval_min,
            "reference_n": baseline.reference_n,
            "deviation_threshold_rel_pct": round(baseline.deviation_threshold_rel * 100, 2),
            "deviation_detection": {
                "target_recall_pct": deviation.target_recall * 100,
                "measured_recall_pct": round(deviation.measured_recall * 100, 2),
                "measured_precision_pct": round(deviation.measured_precision * 100, 2),
                "n_true_deviations": deviation.n_true_deviations,
                "n_flagged": deviation.n_flagged,
                "meets_target": deviation.meets_target,
                "method": "انحراف‌های دانسته>۵٪ به‌صورت مصنوعی تزریق شد و نرخ تشخیص روی آن اندازه‌گیری شد (FR-M2-02)",
            },
        }
        out["energy_timeseries_preview"] = artifacts.get("energy_timeseries", [])[:50]
    else:
        out["energy_baseline"] = {"ready": False, "note": "مدل‌ها هنوز آموزش ندیده‌اند"}
    return out


_frame_cache: dict | None = None


def _training_frame_cached():
    """Re-derive the exact same synthetic frame used at training time, for
    re-running ``evaluate_deviation_detection`` without re-training. Cheap
    (pure numpy/pandas generation, no model fitting) compared to retraining.
    """
    global _frame_cache
    if _frame_cache is None:
        from ..ml.synthetic import generate_training_frame

        artifacts = registry.get_artifacts()
        _frame_cache = generate_training_frame(n_points=artifacts["n_points"], seed=artifacts["seed"])
    return _frame_cache


def feed_constraints(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in rows(conn, "SELECT * FROM feed_batches ORDER BY received_at DESC LIMIT 20")]


def recommend_production_mix(conn: sqlite3.Connection, energy_budget_gj: float | None = None) -> dict:
    """FR-M2-03: a real LP optimizer (scipy.optimize.linprog) over current
    feedstock availability (aggregated from the seeded ``feed_batches``
    table) and illustrative product economics — not a single-output stub.

    Returns >= 3 costed scenarios (see
    backend/app/ml/module2_energy.run_scenarios for the scenario
    definitions and the stoichiometry/price assumptions, all labelled).
    """
    batches = rows(conn, "SELECT feed_type, SUM(quantity_t) AS total_t FROM feed_batches GROUP BY feed_type")
    availability = {b["feed_type"]: b["total_t"] for b in batches}

    if energy_budget_gj is None:
        # NOT derived from the seeded production_records sum: that table
        # is a handful of illustrative random rows (backend/app/seed.py),
        # far too small/arbitrary to stand in for a monthly energy budget
        # (using it made every LP scenario spuriously energy-starved).
        # Default instead to a illustrative fraction of running all three
        # products at their nameplate monthly capacity (docs/SRS.md 2.1) —
        # still a placeholder assumption, but a defensible order of
        # magnitude, and always labelled as illustrative in the response.
        nameplate_energy_gj = sum(
            m2.MONTHLY_CAPACITY_T[p] * m2.ENERGY_INTENSITY_GJ_PER_T[p] for p in m2.PRODUCTS
        )
        energy_budget_gj = nameplate_energy_gj * 0.7

    scenarios = m2.run_scenarios(availability, base_energy_budget_gj=float(energy_budget_gj))
    best = max((s for s in scenarios if s.feasible), key=lambda s: s.profit_usd, default=None)
    return {
        "feed_availability_t": availability,
        "energy_budget_gj": round(float(energy_budget_gj), 1),
        "scenarios": [
            {
                "name": s.name,
                "description": s.description,
                "assumptions_note": s.assumptions_note,
                "production_t": s.production_t,
                "revenue_usd": s.revenue_usd,
                "feed_cost_usd": s.feed_cost_usd,
                "energy_cost_usd": s.energy_cost_usd,
                "profit_usd": s.profit_usd,
                "binding_constraints": s.binding_constraints,
                "feasible": s.feasible,
            }
            for s in scenarios
        ],
        "recommended_scenario": best.name if best else None,
        "is_placeholder": False,
        "optimizer": "scipy.optimize.linprog (LP) — FR-M2-03",
    }
