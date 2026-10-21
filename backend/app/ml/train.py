"""Orchestrates training of all four modules' real models and persists them.

Run via ``scripts/train_models.py`` (CLI) or imported directly. Produces
one joblib bundle (model objects + stats) and one JSON metrics summary —
the JSON is what docs/SRS.md's status column and the frontend's "measured
on synthetic data" banners are meant to read, without needing to
deserialize sklearn objects just to show a number.

Everything here trains on synthetic data only (backend/app/ml/synthetic.py)
— see that module and backend/app/ml/__init__.py for the honesty framing
that must stay attached to every number this produces.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from . import module1_process as m1
from . import module2_energy as m2
from . import module3_quality as m3
from . import module4_forecast as m4
from .synthetic import PROCESS_FEATURE_COLUMNS, generate_training_frame

ARTIFACTS_FILENAME = "artifacts.joblib"
METRICS_FILENAME = "metrics.json"


def _jsonable(obj: Any) -> Any:
    """Best-effort conversion of our dataclasses/tuples into plain JSON."""
    if is_dataclass(obj) and not isinstance(obj, type):
        d = asdict(obj)
        return {k: _jsonable(v) for k, v in d.items() if k != "model"}
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def train_all(
    out_dir: Path,
    n_points: int = 20_000,
    seed: int = 42,
    upset_rate: float = 0.015,
    upset_scale: float = 3.0,
) -> dict:
    """Train everything and write artifacts.joblib + metrics.json to out_dir.

    Returns the metrics dict (same content as metrics.json).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    df = generate_training_frame(n_points=n_points, seed=seed, upset_rate=upset_rate, upset_scale=upset_scale)

    envelopes = m1.compute_operating_envelopes(df)
    correlation = m1.train_productivity_correlation(df)
    mek_correlation = m1.train_mek_productivity_correlation(df)

    energy_baseline = m2.train_energy_baseline(df, interval_min=1.0)
    energy_mae_sanity = m2.regression_sanity_mae(energy_baseline, df)
    deviation_detection = m2.evaluate_deviation_detection(energy_baseline, df)
    enpi_cusum_full = m2.enpi_and_cusum(energy_baseline, df)
    # downsample for storage/charting — this is illustrative of the EnB's
    # behaviour on the synthetic series, not a live production feed
    _step = max(1, len(df) // 400)
    energy_timeseries = [
        {
            "ts": df["timestamp"].iloc[i].isoformat(),
            "enpi": round(float(enpi_cusum_full["enpi"][i]), 4),
            "cusum_gj": round(float(enpi_cusum_full["cusum_gj"][i]), 3),
        }
        for i in range(0, len(df), _step)
    ]

    purity_regressor = m3.train_purity_regressor(df)
    oos_classifier = m3.train_oos_classifier(df)

    forecast_model = m4.train_forecaster(df)
    recent_production_series = m4._aggregate_production_rate(df)[-80:].tolist()

    baseline_features = {c: float(df[c].tail(2000).mean()) for c in PROCESS_FEATURE_COLUMNS}

    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    training_seconds = round(time.time() - t0, 1)

    artifacts = {
        "envelopes": envelopes,
        "correlation": correlation,
        "mek_correlation": mek_correlation,
        "energy_baseline": energy_baseline,
        "purity_regressor": purity_regressor,
        "oos_classifier": oos_classifier,
        "forecast_model": forecast_model,
        "baseline_features": baseline_features,
        "energy_timeseries": energy_timeseries,
        "recent_production_series": recent_production_series,
        "trained_at": trained_at,
        "n_points": n_points,
        "seed": seed,
    }
    joblib.dump(artifacts, out_dir / ARTIFACTS_FILENAME)

    metrics = {
        "trained_at": trained_at,
        "training_seconds": training_seconds,
        "n_points": n_points,
        "seed": seed,
        "data_source": "synthetic (scripts/generate_synthetic_data.py, extended — see backend/app/ml/synthetic.py); NOT real plant data",
        "module1": {
            "envelopes": {tag: _jsonable(env) for tag, env in envelopes.items()},
            "productivity_correlation": _jsonable(correlation),
            "mek_productivity_correlation": _jsonable(mek_correlation),
        },
        "module2": {
            "energy_baseline": _jsonable(energy_baseline),
            "energy_baseline_mae_sanity_gj": energy_mae_sanity,
            "deviation_detection": _jsonable(deviation_detection),
        },
        "module3": {
            "purity_regression": {
                "mae_test_pct": purity_regressor.mae_test_pct,
                "mae_train_pct": purity_regressor.mae_train_pct,
                "target_mae_pct": purity_regressor.target_mae_pct,
                "meets_target": purity_regressor.meets_target,
                "n_train": purity_regressor.n_train,
                "n_test": purity_regressor.n_test,
                "feature_importance": purity_regressor.feature_importance_ranking(),
            },
            "oos_classifier": {
                "decision_threshold": oos_classifier.decision_threshold,
                "tpr_test": oos_classifier.tpr_test,
                "precision_test": oos_classifier.precision_test,
                "auc_test": oos_classifier.auc_test,
                "target_tpr": oos_classifier.target_tpr,
                "meets_target": oos_classifier.meets_target,
                "n_test": oos_classifier.n_test,
                "n_positive_test": oos_classifier.n_positive_test,
            },
        },
        "module4": {
            "forecast": {
                "rmse_pct_by_horizon_h": forecast_model.rmse_pct_by_horizon_h,
                "overall_rmse_pct": forecast_model.overall_rmse_pct,
                "target_rmse_pct": forecast_model.target_rmse_pct,
                "meets_target": forecast_model.meets_target,
            }
        },
    }
    with open(out_dir / METRICS_FILENAME, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    return metrics
