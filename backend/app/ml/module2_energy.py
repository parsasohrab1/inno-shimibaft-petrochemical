"""Module 2 training — ISO 50001-style energy baseline + a real LP optimizer.

FR-M2-01/02: replaces the flat-average Energy Intensity baseline with a
proper Energy Baseline (EnB) regression — energy consumption (GJ) as a
function of a relevant variable (production tonnage), fit on a
"reference period" of stable/baseline operation, the pattern used by the
Khorasan Petrochemical SEM project's ``energy_perf.py`` on this account
(ISO 50001 / ISO 50006 EnB + EnPI + CUSUM). From that:
  - EnPI(t) = actual energy / EnB-predicted energy (ratio; 1.0 = exactly
    on baseline).
  - CUSUM(t) = running cumulative sum of (actual - predicted) GJ, the
    standard ISO 50001 tool for spotting a sustained drift rather than
    single-point noise.
  - a deviation flag, calibrated on the reference period's own residual
    spread, used below to MEASURE (not assume) FR-M2-02's detection-rate
    criterion on a held-out test period with synthetically injected
    deviations of known size.

FR-M2-03: a real constrained production-mix optimizer using
``scipy.optimize.linprog`` (an LP, chosen over a MILP/PuLP dependency
because the mix here is genuinely continuous — no integer batch/lot
constraints have been specified by the client). All prices, feed costs
and stoichiometric yields below are ILLUSTRATIVE ASSUMPTIONS (the MTBE
yield coefficients are real stoichiometry — isobutylene 56 g/mol +
methanol 32 g/mol -> MTBE 88 g/mol — the others are reasonable
placeholders), clearly labelled as such in every API response; nothing
here is a real negotiated price or a vendor-confirmed yield.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

from .synthetic import chronological_split

# --- FR-M2-01/02: ISO-50001-style Energy Baseline -------------------------


@dataclass
class EnergyBaseline:
    intercept: float
    slope_gj_per_t: float
    reference_n: int
    residual_std_gj: float
    deviation_threshold_rel: float  # relative-residual threshold used to flag a deviation
    interval_min: float = 1.0  # sampling interval the intercept was fit at — see predict_energy_gj


def train_energy_baseline(df, reference_frac: float = 0.4, interval_min: float = 1.0) -> EnergyBaseline:
    """Fit EnB = intercept + slope * production_t on a reference period.

    The reference period is the first ``reference_frac`` of the series,
    standing in for a period of confirmed stable/baseline operation (ISO
    50001 requires the client to designate this; the scaffold had no real
    period to designate, so this is the best available substitute on
    synthetic data).

    ``interval_min`` is the sampling interval of ``df`` (minutes — matches
    the ``freq_min`` the caller built ``df`` with). The fitted
    ``intercept`` represents FIXED/baseline energy per THAT interval (e.g.
    idle steam/utility draw), not a universal constant — see
    ``predict_energy_gj`` for why callers must not reuse it unscaled at a
    different interval (this was a real bug caught while wiring module 4's
    what-if re-simulation: plugging a 15-minute production amount into a
    baseline fit on 1-minute intervals silently under-counted overhead
    energy by ~15x).
    """
    n_ref = max(10, int(len(df) * reference_frac))
    ref = df.iloc[:n_ref]
    X = ref[["production_t"]].to_numpy()
    y = ref["energy_gj"].to_numpy()
    model = LinearRegression().fit(X, y)
    resid = y - model.predict(X)
    resid_std = float(np.std(resid, ddof=1))
    rel_resid = resid / np.maximum(model.predict(X), 1e-6)
    # calibrate the "this looks like a deviation" threshold from the
    # reference period's own relative-residual spread (mean + 2*std),
    # rather than hard-coding the 5% acceptance-criterion number itself
    threshold = float(np.mean(np.abs(rel_resid)) + 2 * np.std(rel_resid))
    return EnergyBaseline(
        intercept=round(float(model.intercept_), 4),
        slope_gj_per_t=round(float(model.coef_[0]), 6),
        reference_n=n_ref,
        residual_std_gj=round(resid_std, 4),
        deviation_threshold_rel=round(threshold, 4),
        interval_min=interval_min,
    )


def predict_energy_gj(baseline: EnergyBaseline, production_t: float, interval_min: float | None = None) -> float:
    """Predict total GJ for ``production_t`` tons produced over an interval.

    The fixed/overhead ``intercept`` was fit at ``baseline.interval_min``
    minutes per row; if the caller's interval differs (e.g. module 4
    aggregates to 15-minute bins while training used 1-minute rows), the
    intercept is scaled proportionally to the interval length so the
    fixed-overhead *rate* (GJ/min of idle draw) stays consistent instead
    of being silently reused as if it were interval-independent.
    """
    scale = 1.0 if interval_min is None else interval_min / baseline.interval_min
    return baseline.intercept * scale + baseline.slope_gj_per_t * production_t


def enpi_and_cusum(baseline: EnergyBaseline, df) -> dict:
    predicted = baseline.intercept + baseline.slope_gj_per_t * df["production_t"].to_numpy()
    actual = df["energy_gj"].to_numpy()
    predicted_safe = np.maximum(predicted, 1e-6)
    enpi = actual / predicted_safe
    cusum = np.cumsum(actual - predicted)
    return {
        "enpi": enpi,
        "cusum_gj": cusum,
        "predicted_gj": predicted,
        "actual_gj": actual,
    }


@dataclass
class DeviationDetectionResult:
    measured_recall: float
    measured_precision: float
    n_true_deviations: int
    n_flagged: int
    n_true_positive: int
    meets_target: bool
    target_recall: float = 0.80


def evaluate_deviation_detection(baseline: EnergyBaseline, df, rng_seed: int = 123) -> DeviationDetectionResult:
    """Measure FR-M2-02's ">=80% of >5% deviations detected" on a held-out
    test period with synthetically injected deviations of KNOWN size.

    This is the only honest way to measure a detection rate without real
    pilot-test incident data (SRS's own acceptance test): we take the
    test-period energy values, and for a random subset of rows inflate
    the actual energy by a known percentage (some > 5%, some <= 5% as
    negative controls), then check whether the EnB+threshold rule flags
    exactly the rows we inflated past 5%.
    """
    _, test_idx = chronological_split(len(df))
    test = df.iloc[test_idx].reset_index(drop=True)
    rng = np.random.default_rng(rng_seed)

    production = test["production_t"].to_numpy()
    base_actual = test["energy_gj"].to_numpy()
    predicted = baseline.intercept + baseline.slope_gj_per_t * production
    predicted_safe = np.maximum(predicted, 1e-6)

    n = len(test)
    # candidate injected deviation sizes: half are >5% (true positives
    # we expect to catch), half are small decoys (<=5%, should NOT count
    # against recall; some may still trip the threshold - that's a
    # precision cost we report honestly rather than hide)
    injected_pct = rng.choice([0.06, 0.08, 0.12, 0.20, 0.02, 0.03, 0.04], size=n)
    inflated_actual = base_actual * (1 + injected_pct)

    rel_residual = (inflated_actual - predicted_safe) / predicted_safe
    flagged = np.abs(rel_residual) > baseline.deviation_threshold_rel
    is_true_deviation = injected_pct > 0.05

    n_true = int(is_true_deviation.sum())
    n_flagged = int(flagged.sum())
    n_tp = int(np.logical_and(flagged, is_true_deviation).sum())
    recall = n_tp / n_true if n_true else 0.0
    precision = n_tp / n_flagged if n_flagged else 0.0

    return DeviationDetectionResult(
        measured_recall=round(recall, 4),
        measured_precision=round(precision, 4),
        n_true_deviations=n_true,
        n_flagged=n_flagged,
        n_true_positive=n_tp,
        meets_target=recall >= 0.80,
    )


def regression_sanity_mae(baseline: EnergyBaseline, df) -> float:
    _, test_idx = chronological_split(len(df))
    test = df.iloc[test_idx]
    pred = baseline.intercept + baseline.slope_gj_per_t * test["production_t"].to_numpy()
    return round(float(mean_absolute_error(test["energy_gj"], pred)), 4)


# --- FR-M2-03: LP production-mix optimizer ---------------------------------

# ILLUSTRATIVE ASSUMPTIONS — see module docstring. MTBE yields are real
# stoichiometry; everything else (prices, Raffinate-2/MEK yields, energy
# intensities, energy cost) is a reasonable placeholder, not vendor data.
ISOBUTYLENE_MW = 56.1
METHANOL_MW = 32.0
MTBE_MW = 88.1
RAFFINATE1_PER_T_MTBE = ISOBUTYLENE_MW / MTBE_MW       # ~0.637 t raffinate-1 (isobutylene-equiv) per t MTBE
METHANOL_PER_T_MTBE = METHANOL_MW / MTBE_MW             # ~0.363 t methanol per t MTBE
RAFFINATE1_PER_T_RAFFINATE2 = 1.0                        # illustrative: unreacted C4 carried through ~1:1
BUTENES_PER_T_MEK = 1.0 / 0.95                           # illustrative 95% yield MEK from n/iso-butenes

PRICE_USD_PER_T = {"MTBE": 700.0, "C4 Raffinate-2": 500.0, "MEK": 900.0}
FEED_COST_USD_PER_T = {"C4 Raffinate-1 (mixed C4)": 550.0, "Methanol": 300.0, "n/iso-Butenes (برای MEK)": 500.0}
ENERGY_COST_USD_PER_GJ = 15.0
ENERGY_INTENSITY_GJ_PER_T = {"MTBE": 8.5, "C4 Raffinate-2": 1.0, "MEK": 12.0}

# monthly capacity, derived from docs/SRS.md 2.1 annual nameplate capacities / 12
MONTHLY_CAPACITY_T = {"MTBE": 90_000 / 12, "C4 Raffinate-2": 50_000 / 12, "MEK": 50_000 / 12}

PRODUCTS = ["MTBE", "C4 Raffinate-2", "MEK"]


@dataclass
class MixScenario:
    name: str
    description: str
    assumptions_note: str
    production_t: dict[str, float]
    revenue_usd: float
    feed_cost_usd: float
    energy_cost_usd: float
    profit_usd: float
    binding_constraints: list[str]
    feasible: bool


def _solve_mix(
    raffinate1_t: float,
    methanol_t: float,
    butenes_t: float,
    energy_budget_gj: float,
    capacity_scale: float = 1.0,
) -> tuple[np.ndarray, bool, dict]:
    """x = [MTBE_t, Raffinate2_t, MEK_t]; minimize -profit s.t. constraints."""
    profit_coeffs = np.array(
        [
            PRICE_USD_PER_T["MTBE"] - RAFFINATE1_PER_T_MTBE * FEED_COST_USD_PER_T["C4 Raffinate-1 (mixed C4)"]
            - METHANOL_PER_T_MTBE * FEED_COST_USD_PER_T["Methanol"]
            - ENERGY_INTENSITY_GJ_PER_T["MTBE"] * ENERGY_COST_USD_PER_GJ,
            PRICE_USD_PER_T["C4 Raffinate-2"]
            - RAFFINATE1_PER_T_RAFFINATE2 * FEED_COST_USD_PER_T["C4 Raffinate-1 (mixed C4)"]
            - ENERGY_INTENSITY_GJ_PER_T["C4 Raffinate-2"] * ENERGY_COST_USD_PER_GJ,
            PRICE_USD_PER_T["MEK"] - BUTENES_PER_T_MEK * FEED_COST_USD_PER_T["n/iso-Butenes (برای MEK)"]
            - ENERGY_INTENSITY_GJ_PER_T["MEK"] * ENERGY_COST_USD_PER_GJ,
        ]
    )
    c = -profit_coeffs  # linprog minimizes

    A_ub = [
        [RAFFINATE1_PER_T_MTBE, RAFFINATE1_PER_T_RAFFINATE2, 0.0],  # raffinate-1 use
        [METHANOL_PER_T_MTBE, 0.0, 0.0],  # methanol use
        [0.0, 0.0, BUTENES_PER_T_MEK],  # butenes use
        [
            ENERGY_INTENSITY_GJ_PER_T["MTBE"],
            ENERGY_INTENSITY_GJ_PER_T["C4 Raffinate-2"],
            ENERGY_INTENSITY_GJ_PER_T["MEK"],
        ],  # energy budget
    ]
    b_ub = [raffinate1_t, methanol_t, butenes_t, energy_budget_gj]
    bounds = [
        (0, MONTHLY_CAPACITY_T["MTBE"] * capacity_scale),
        (0, MONTHLY_CAPACITY_T["C4 Raffinate-2"] * capacity_scale),
        (0, MONTHLY_CAPACITY_T["MEK"] * capacity_scale),
    ]

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    binding = []
    if res.success:
        slack = np.array(b_ub) - np.array(A_ub) @ res.x
        names = ["raffinate-1 availability", "methanol availability", "n/iso-butenes availability", "energy budget"]
        binding = [n for n, s in zip(names, slack) if s < 1e-3]
    return res.x if res.success else np.zeros(3), bool(res.success), {"binding": binding, "profit": -res.fun if res.success else 0.0}


def run_scenarios(feed_availability: dict[str, float], base_energy_budget_gj: float) -> list[MixScenario]:
    """>=3 real costed scenarios (FR-M2-03), solved by LP, not a stub.

    ``feed_availability`` keys match backend/app/seed.py's feed_type
    strings; a type not present is treated as 0 available.
    """
    raffinate1 = feed_availability.get("C4 Raffinate-1 (mixed C4)", 0.0)
    methanol = feed_availability.get("Methanol", 0.0)
    butenes = feed_availability.get("n/iso-Butenes (برای MEK)", 0.0)

    defs = [
        ("baseline", "فعلی: موجودی خوراک و بودجه انرژی گزارش‌شده", 1.0, 1.0),
        ("feed_constrained", "اختلال خوراک: ۲۰٪ کاهش موجودی رافینیت ۱ و متانول (فرضی)", 0.8, 1.0),
        ("energy_constrained", "محدودیت انرژی: ۱۵٪ کاهش بودجه انرژی (مثلاً سهمیه‌بندی/تعرفه، فرضی)", 1.0, 0.85),
        ("max_margin", "حداکثر ظرفیت: بدون محدودیت خوراک/انرژی فرضی (سقف فقط ظرفیت اسمی)", 5.0, 5.0),
    ]
    out = []
    for name, desc, feed_scale, energy_scale in defs:
        x, feasible, meta = _solve_mix(
            raffinate1 * feed_scale if name != "max_margin" else raffinate1 * 50,
            methanol * feed_scale if name != "max_margin" else methanol * 50,
            butenes * feed_scale if name != "max_margin" else butenes * 50,
            base_energy_budget_gj * energy_scale if name != "max_margin" else base_energy_budget_gj * 50,
        )
        production = {p: round(float(v), 2) for p, v in zip(PRODUCTS, x)}
        revenue = sum(PRICE_USD_PER_T[p] * production[p] for p in PRODUCTS)
        feed_cost = (
            RAFFINATE1_PER_T_MTBE * production["MTBE"] * FEED_COST_USD_PER_T["C4 Raffinate-1 (mixed C4)"]
            + METHANOL_PER_T_MTBE * production["MTBE"] * FEED_COST_USD_PER_T["Methanol"]
            + RAFFINATE1_PER_T_RAFFINATE2 * production["C4 Raffinate-2"] * FEED_COST_USD_PER_T["C4 Raffinate-1 (mixed C4)"]
            + BUTENES_PER_T_MEK * production["MEK"] * FEED_COST_USD_PER_T["n/iso-Butenes (برای MEK)"]
        )
        energy_gj = sum(ENERGY_INTENSITY_GJ_PER_T[p] * production[p] for p in PRODUCTS)
        energy_cost = energy_gj * ENERGY_COST_USD_PER_GJ
        profit = revenue - feed_cost - energy_cost
        out.append(
            MixScenario(
                name=name,
                description=desc,
                assumptions_note="قیمت‌ها/بازده‌ها فرضی‌اند مگر بازده MTBE که استوکیومتری واقعی است؛ داده قیمت واقعی از کارفرما دریافت نشده",
                production_t=production,
                revenue_usd=round(revenue, 1),
                feed_cost_usd=round(feed_cost, 1),
                energy_cost_usd=round(energy_cost, 1),
                profit_usd=round(profit, 1),
                binding_constraints=meta["binding"],
                feasible=feasible,
            )
        )
    return out
