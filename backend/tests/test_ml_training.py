"""Direct tests of backend/app/ml/* training/inference paths — independent
of the FastAPI layer (backend/tests/test_modules.py covers that side).

Uses small synthetic datasets (not the API fixtures' trained_models_dir)
so these stay fast and can assert on exact structural invariants.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.ml import module1_process as m1
from app.ml import module2_energy as m2
from app.ml import module3_quality as m3
from app.ml import module4_forecast as m4
from app.ml.synthetic import generate_training_frame, generate_mtbe_synthetic_data


@pytest.fixture(scope="module")
def small_df():
    return generate_training_frame(n_points=4000, seed=1, upset_rate=0.02, upset_scale=3.5)


def test_generator_default_call_unchanged_by_upset_extension():
    """upset_rate=0 (the default) must reproduce the ORIGINAL SRS-sourced
    function's output bit-for-bit — the extension must be fully opt-in."""
    a = generate_mtbe_synthetic_data(n_points=500, seed=42)
    b = generate_mtbe_synthetic_data(n_points=500, seed=42, upset_rate=0.0)
    assert a.equals(b)


def test_module1_operating_envelopes_are_data_driven(small_df):
    envelopes = m1.compute_operating_envelopes(small_df)
    assert set(envelopes) == {"TI-101", "PI-102", "FI-103", "FI-301", "EI-401"}
    ti101 = envelopes["TI-101"]
    lo, hi = ti101.ci95_of_mean
    assert lo < ti101.mean < hi
    band_lo, band_hi = ti101.operating_band_p2_5_97_5
    assert band_lo < band_hi


def test_module1_correlation_uses_at_least_5_variables(small_df):
    corr = m1.train_productivity_correlation(small_df)
    assert len(corr.features) >= 5
    assert 0.0 <= corr.r2_test <= 1.0
    assert corr.n_train > 0 and corr.n_test > 0


def test_module2_energy_baseline_and_deviation_detection(small_df):
    baseline = m2.train_energy_baseline(small_df, interval_min=1.0)
    assert baseline.slope_gj_per_t != 0
    mae = m2.regression_sanity_mae(baseline, small_df)
    assert mae >= 0

    result = m2.evaluate_deviation_detection(baseline, small_df)
    assert 0.0 <= result.measured_recall <= 1.0
    assert 0.0 <= result.measured_precision <= 1.0
    assert result.n_true_deviations > 0


def test_module2_predict_energy_gj_scales_intercept_by_interval():
    """Regression test for the unit-consistency bug caught while wiring
    module 4: the fixed-overhead intercept must scale with the requested
    interval, not be reused unchanged at a different granularity."""
    baseline = m2.EnergyBaseline(
        intercept=10.0, slope_gj_per_t=2.0, reference_n=100, residual_std_gj=0.1, deviation_threshold_rel=0.1,
        interval_min=1.0,
    )
    at_training_interval = m2.predict_energy_gj(baseline, production_t=5.0, interval_min=1.0)
    at_15x_interval = m2.predict_energy_gj(baseline, production_t=5.0, interval_min=15.0)
    assert at_training_interval == pytest.approx(10.0 + 2.0 * 5.0)
    assert at_15x_interval == pytest.approx(10.0 * 15.0 + 2.0 * 5.0)


def test_module2_lp_optimizer_produces_feasible_costed_scenarios():
    scenarios = m2.run_scenarios(
        {"C4 Raffinate-1 (mixed C4)": 500, "Methanol": 200, "n/iso-Butenes (برای MEK)": 300},
        base_energy_budget_gj=20000,
    )
    assert len(scenarios) >= 3
    assert any(s.feasible for s in scenarios)
    for s in scenarios:
        assert set(s.production_t) == {"MTBE", "C4 Raffinate-2", "MEK"}
        assert all(v >= 0 for v in s.production_t.values())


def test_module3_purity_regressor_and_oos_classifier(small_df):
    reg = m3.train_purity_regressor(small_df)
    assert reg.mae_test_pct >= 0
    assert reg.n_train > 0 and reg.n_test > 0
    ranking = reg.feature_importance_ranking()
    assert len(ranking) >= 3  # FR-M3-03's >= 3 ranked factors
    assert sum(r["importance"] for r in ranking) == pytest.approx(1.0, abs=1e-3)  # sklearn importances sum to 1
    # current purity must never be a feature (LIMS-lag honesty rule)
    assert "mtbe_purity_pct" not in reg.features

    clf = m3.train_oos_classifier(small_df, target_recall=0.85)
    assert "mtbe_purity_pct" not in clf.features
    assert 0.0 <= clf.tpr_test <= 1.0
    assert 0.0 <= clf.precision_test <= 1.0


def test_module3_predict_purity_and_oos_probability_are_bounded(small_df):
    reg = m3.train_purity_regressor(small_df)
    clf = m3.train_oos_classifier(small_df)
    sample = {f: float(small_df[f].iloc[-1]) for f in reg.features}
    purity = m3.predict_purity(reg, sample)
    assert 90.0 <= purity <= 100.0

    clf_sample = {f: float(small_df[f].iloc[-1]) if f in small_df.columns else 0.0 for f in clf.features}
    proba = m3.predict_oos_probability(clf, clf_sample)
    assert 0.0 <= proba <= 1.0


def test_module4_forecaster_and_resimulation(small_df):
    model = m4.train_forecaster(small_df)
    assert model.overall_rmse_pct >= 0
    series = m4._aggregate_production_rate(small_df)[-40:]
    forecast = m4.forecast_from_recent(model, series, horizon_hours=1)
    assert len(forecast) == 60 // model.freq_min

    baseline = m2.train_energy_baseline(small_df, interval_min=1.0)
    reg = m3.train_purity_regressor(small_df)
    baseline_features = {c: float(small_df[c].tail(500).mean()) for c in m4.WHATIF_PARAMETERS}

    result = m4.resimulate(baseline_features, reg, baseline, "reactor_temp_C", 1.0)
    assert result.baseline["predicted_purity_pct"] != result.scenario["predicted_purity_pct"]

    with pytest.raises(ValueError):
        m4.resimulate(baseline_features, reg, baseline, "not_a_real_parameter", 1.0)

    ranked = m4.rank_scenarios(baseline_features, reg, baseline)
    assert len(ranked) >= 3
    assert ranked == sorted(ranked, key=lambda s: -s.score)  # sorted descending by score
