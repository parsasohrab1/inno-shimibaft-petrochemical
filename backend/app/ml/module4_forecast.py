"""Module 4 training — a real forecaster + a genuine cross-module what-if.

FR-M4-01: a Holt's linear-trend exponential-smoothing forecaster (hand
-rolled in numpy — no statsmodels dependency needed for something this
simple) for the 1-8h-ahead production rate, evaluated by rolling-origin
backtesting on a held-out period and reported as RMSE relative to the
mean actual rate (the SRS criterion, "RMSE <= 5%", is itself expressed as
a percentage, not an absolute GJ/t or kg/h number).

FR-M2-04 / FR-M4-03: ``what_if`` (in services/forecasting_decision.py,
calling into ``resimulate`` below) now actually calls module 3's trained
purity regressor and module 2's trained energy baseline with the
perturbed input — it is a real, if small, re-simulation across modules,
not a scalar multiply on a historical sum.

FR-M4-03: >=3 scenarios, scored on production / quality-margin / energy
with a simple weighted multi-criteria score, then ranked.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import module2_energy as m2
from . import module3_quality as m3
from .synthetic import MTBE_PURITY_SPEC_MIN, PROCESS_FEATURE_COLUMNS, chronological_split

FORECAST_FREQ_MIN = 15  # aggregate to 15-min bins (SRS 3.2.1's energy-data cadence) before forecasting
HORIZON_HOURS = (1, 2, 4, 8)


@dataclass
class HoltParams:
    alpha: float
    beta: float


def _holt_fit_predict(series: np.ndarray, alpha: float, beta: float, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """Fit Holt's linear trend model in-sample and forecast ``horizon`` steps.

    Returns (in_sample_one_step_fitted, forecast_vector[1..horizon]).
    """
    n = len(series)
    level = series[0]
    trend = series[1] - series[0] if n > 1 else 0.0
    fitted = np.empty(n)
    fitted[0] = level
    for i in range(1, n):
        y = series[i]
        prev_level = level
        level = alpha * y + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
        fitted[i] = prev_level + trend
    forecast = level + (np.arange(1, horizon + 1)) * trend
    return fitted, forecast


def _grid_search_holt(series: np.ndarray) -> HoltParams:
    best = HoltParams(0.3, 0.1)
    best_err = np.inf
    for alpha in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        for beta in (0.02, 0.05, 0.1, 0.2, 0.3):
            fitted, _ = _holt_fit_predict(series, alpha, beta, horizon=1)
            err = np.mean((series[1:] - fitted[1:]) ** 2)
            if err < best_err:
                best_err, best = err, HoltParams(alpha, beta)
    return best


@dataclass
class ForecastModel:
    params: HoltParams
    freq_min: int
    rmse_pct_by_horizon_h: dict[int, float]
    overall_rmse_pct: float
    target_rmse_pct: float = 5.0

    @property
    def meets_target(self) -> bool:
        return self.overall_rmse_pct <= self.target_rmse_pct


def _aggregate_production_rate(df) -> np.ndarray:
    """Bin the 1-min synthetic series into FORECAST_FREQ_MIN-minute means
    of product_flow_kg_h — a steadier series than the raw 1-min signal,
    consistent with how a real production-rate forecast would be built on
    smoothed/aggregated data rather than raw noisy instrument ticks.
    """
    bin_size = FORECAST_FREQ_MIN  # df is at 1-min resolution
    n_bins = len(df) // bin_size
    trimmed = df["product_flow_kg_h"].to_numpy()[: n_bins * bin_size]
    return trimmed.reshape(n_bins, bin_size).mean(axis=1)


def train_forecaster(df) -> ForecastModel:
    series = _aggregate_production_rate(df)
    train_idx, test_idx = chronological_split(len(series))
    train_series = series[train_idx]
    params = _grid_search_holt(train_series)

    steps_per_hour = 60 // FORECAST_FREQ_MIN
    rmse_by_h: dict[int, float] = {}
    mean_actual = float(np.mean(series))

    test_start = test_idx.start
    for h in HORIZON_HOURS:
        horizon_steps = h * steps_per_hour
        errors = []
        # rolling-origin backtest: refit the smoothing state up to each
        # origin using everything before it, forecast horizon_steps ahead
        for origin in range(test_start, len(series) - horizon_steps, max(1, horizon_steps // 2)):
            history = series[:origin]
            if len(history) < 5:
                continue
            _, forecast = _holt_fit_predict(history, params.alpha, params.beta, horizon_steps)
            actual = series[origin + horizon_steps - 1]
            predicted = forecast[-1]
            errors.append((actual - predicted) ** 2)
        if errors:
            rmse = float(np.sqrt(np.mean(errors)))
            rmse_by_h[h] = round(100 * rmse / mean_actual, 3)

    overall = round(float(np.mean(list(rmse_by_h.values()))), 3) if rmse_by_h else float("nan")
    return ForecastModel(
        params=params, freq_min=FORECAST_FREQ_MIN, rmse_pct_by_horizon_h=rmse_by_h, overall_rmse_pct=overall
    )


def forecast_from_recent(model: ForecastModel, recent_series: np.ndarray, horizon_hours: int) -> list[float]:
    steps = horizon_hours * (60 // model.freq_min)
    _, forecast = _holt_fit_predict(recent_series, model.params.alpha, model.params.beta, steps)
    return [round(float(v), 2) for v in forecast]


# --- FR-M2-04 / FR-M4-03: real cross-module re-simulation ------------------

WHATIF_PARAMETERS = PROCESS_FEATURE_COLUMNS  # reactor_temp_C, reactor_pressure_MPa, feed_flow_kg_h, meoh_isobutene_ratio


@dataclass
class ResimResult:
    baseline: dict
    scenario: dict
    parameter: str
    delta_pct: float


def resimulate(
    baseline_features: dict[str, float],
    purity_model: m3.PurityRegressionResult,
    energy_baseline: m2.EnergyBaseline,
    parameter: str,
    delta_pct: float,
) -> ResimResult:
    """Perturb one DCS-tag feature and re-run modules 2-3's trained models.

    This is the real replacement for the old linear-percentage ``what_if``
    placeholder: it literally calls module 3's purity regressor and
    module 2's energy baseline with the new feature vector, rather than
    scaling a historical total by ``delta_pct``.
    """
    if parameter not in WHATIF_PARAMETERS:
        raise ValueError(f"ناشناخته: {parameter} — باید یکی از {WHATIF_PARAMETERS} باشد")

    def _evaluate(features: dict[str, float]) -> dict:
        purity = m3.predict_purity(purity_model, features)
        production_kg_h = features["feed_flow_kg_h"] * (purity / 100.0)
        production_t_per_15min = production_kg_h * (FORECAST_FREQ_MIN / 60.0) / 1000.0
        energy_gj = m2.predict_energy_gj(energy_baseline, production_t_per_15min, interval_min=FORECAST_FREQ_MIN)
        energy_intensity = energy_gj / production_t_per_15min if production_t_per_15min > 0 else float("inf")
        return {
            "features": features,
            "predicted_purity_pct": round(purity, 3),
            "oos_margin_pct": round(purity - MTBE_PURITY_SPEC_MIN, 3),
            "production_rate_kg_h": round(production_kg_h, 1),
            "predicted_energy_intensity_gj_per_t": round(energy_intensity, 4),
        }

    baseline_eval = _evaluate(baseline_features)
    scenario_features = dict(baseline_features)
    scenario_features[parameter] = baseline_features[parameter] * (1 + delta_pct / 100.0)
    scenario_eval = _evaluate(scenario_features)

    return ResimResult(baseline=baseline_eval, scenario=scenario_eval, parameter=parameter, delta_pct=delta_pct)


@dataclass
class ScoredScenario:
    name: str
    delta: dict[str, float]  # {parameter: delta_pct}
    production_rate_kg_h: float
    predicted_purity_pct: float
    predicted_energy_intensity_gj_per_t: float
    score: float


def rank_scenarios(
    baseline_features: dict[str, float],
    purity_model: m3.PurityRegressionResult,
    energy_baseline: m2.EnergyBaseline,
    weights: dict[str, float] | None = None,
) -> list[ScoredScenario]:
    """FR-M4-03: >=3 alternative operating scenarios, each actually
    re-simulated through modules 2-3, ranked by a weighted multi-criteria
    score (production: higher is better; quality margin above spec:
    higher is better; energy intensity: lower is better).
    """
    weights = weights or {"production": 0.4, "quality": 0.3, "energy": 0.3}

    candidates: list[tuple[str, dict[str, float]]] = [
        ("baseline", {}),
        ("دمای راکتور +۰.۵٪", {"reactor_temp_C": 0.5}),
        ("نسبت خوراک به سمت نقطه بهینه (-۱٪)", {"meoh_isobutene_ratio": -1.0}),
        ("دبی خوراک +۳٪", {"feed_flow_kg_h": 3.0}),
    ]

    evaluated = []
    for name, deltas in candidates:
        features = dict(baseline_features)
        for p, d in deltas.items():
            features[p] = features[p] * (1 + d / 100.0)
        purity = m3.predict_purity(purity_model, features)
        production_kg_h = features["feed_flow_kg_h"] * (purity / 100.0)
        production_t = production_kg_h * (FORECAST_FREQ_MIN / 60.0) / 1000.0
        energy_gj = m2.predict_energy_gj(energy_baseline, production_t, interval_min=FORECAST_FREQ_MIN)
        ei = energy_gj / production_t if production_t > 0 else float("inf")
        evaluated.append((name, deltas, production_kg_h, purity, ei))

    prod_vals = [e[2] for e in evaluated]
    purity_vals = [e[3] for e in evaluated]
    ei_vals = [e[4] for e in evaluated]

    def norm(vals, v, invert=False):
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-9:
            return 0.5
        n = (v - lo) / (hi - lo)
        return 1 - n if invert else n

    scored = []
    for name, deltas, prod, purity, ei in evaluated:
        score = (
            weights["production"] * norm(prod_vals, prod)
            + weights["quality"] * norm(purity_vals, purity)
            + weights["energy"] * norm(ei_vals, ei, invert=True)
        )
        scored.append(
            ScoredScenario(
                name=name,
                delta=deltas,
                production_rate_kg_h=round(prod, 1),
                predicted_purity_pct=round(purity, 3),
                predicted_energy_intensity_gj_per_t=round(ei, 4),
                score=round(float(score), 4),
            )
        )
    return sorted(scored, key=lambda s: -s.score)
