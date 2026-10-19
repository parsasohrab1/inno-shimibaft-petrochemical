"""Synthetic training-data generation and shared feature engineering.

Wraps the official ``generate_mtbe_synthetic_data`` function (the one
reproduced verbatim-in-logic from docs/SRS.md section 3.2.4, now living in
scripts/generate_synthetic_data.py) and adds the feature columns that
modules 1 and 3 train against. No real plant data is used anywhere here.

Honesty notes baked into the feature design (read before changing it):
  - MTBE purity (LIMS) is assumed to lag up to 24h in reality (SRS 2.3).
    So the OOS-classifier features below deliberately EXCLUDE the current
    purity value — only DCS-available process tags (temperature,
    pressure, feed flow, feed ratio) are used as predictors, both for the
    purity regressor (module 3's whole point is estimating the lagged lab
    value from real-time tags) and for the forward-looking OOS
    classifier. Using current purity as a classifier feature would leak
    the very quantity the real system does not have in real time.
  - ``product_flow_kg_h`` and ``production_t`` are ENGINEERED PROXIES for
    the FI-301 product-flow tag, which the synthetic generator does not
    emit directly. They are modelled as
    ``feed_flow_kg_h * (mtbe_purity_pct / 100)`` — i.e. a simple
    yield-adjusted mass balance (more feed and higher purity => more
    on-spec product). This is a real, physically-motivated engineering
    relationship (not a tautology to inflate R^2): module 1's correlation
    analysis in module1_process.py reports this plainly in its docstring.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATOR_PATH = _REPO_ROOT / "scripts" / "generate_synthetic_data.py"


def _load_official_generator():
    """Import generate_mtbe_synthetic_data straight from its source file.

    Avoids depending on ``scripts`` being an importable package (it has no
    __init__.py) or on the caller's sys.path/cwd.
    """
    spec = importlib.util.spec_from_file_location("_spro_synth_gen", _GENERATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_spro_synth_gen", module)
    spec.loader.exec_module(module)
    return module.generate_mtbe_synthetic_data


generate_mtbe_synthetic_data = _load_official_generator()

# Reactor pressure is not part of the purity/energy formula at all (see the
# generator docstring) — it is still offered as a feature/regressor because
# a real engineer would not know that in advance from tag metadata alone,
# and module 3's feature-importance ranking is expected to (correctly)
# rank it low. Keeping it in is itself part of the honesty story.
PROCESS_FEATURE_COLUMNS = [
    "reactor_temp_C",
    "reactor_pressure_MPa",
    "feed_flow_kg_h",
    "meoh_isobutene_ratio",
]

MTBE_PURITY_SPEC_MIN = 97.0  # matches backend/app/seed.py lab_specs for ("MTBE", "purity_pct")

# docs/SRS.md 3.2.2 tag mapping for the columns this package actually models
TAG_TO_SYNTHETIC_COLUMN = {
    "TI-101": "reactor_temp_C",
    "PI-102": "reactor_pressure_MPa",
    "FI-103": "feed_flow_kg_h",
    "FI-301": "product_flow_kg_h",  # engineered proxy — see module docstring
    "EI-401": "energy_intensity_GJ_t",
}


def generate_training_frame(
    n_points: int = 20_000,
    freq_min: int = 1,
    seed: int = 42,
    upset_rate: float = 0.015,
    upset_scale: float = 3.0,
) -> pd.DataFrame:
    """The base MTBE time series plus engineered productivity/rolling columns.

    ``upset_rate``/``upset_scale`` are forwarded to the (otherwise
    untouched) official generator — see its docstring. Defaults here are
    tuned (empirically, on this synthetic generator only) to produce a
    workable, non-degenerate rate of >minutes-ahead out-of-spec events for
    module 3's classifier (roughly 1-2% of rows), while leaving the
    default call (``upset_rate=0``) bit-for-bit identical to the original
    SRS-sourced function.
    """
    df = generate_mtbe_synthetic_data(
        n_points=n_points, freq_min=freq_min, seed=seed, upset_rate=upset_rate, upset_scale=upset_scale
    )
    df["product_flow_kg_h"] = df["feed_flow_kg_h"] * (df["mtbe_purity_pct"] / 100.0)
    # tons produced in this sample's interval, for module-2's energy baseline
    df["production_t"] = df["product_flow_kg_h"] * (freq_min / 60.0) / 1000.0
    df["energy_gj"] = df["energy_intensity_GJ_t"] * df["production_t"]

    # rolling, DCS-available-only features (no future leakage: center=False)
    win = max(5, int(round(10 / max(freq_min, 1))))  # ~10 minutes of points
    for col in ("reactor_temp_C", "meoh_isobutene_ratio"):
        df[f"{col}_roll_mean"] = df[col].rolling(win, min_periods=1).mean()
        df[f"{col}_roll_std"] = df[col].rolling(win, min_periods=1).std().fillna(0.0)
        df[f"{col}_slope"] = df[col].diff(win).fillna(0.0) / win
    return df


def oos_feature_columns() -> list[str]:
    return PROCESS_FEATURE_COLUMNS + [
        "reactor_temp_C_roll_mean",
        "reactor_temp_C_roll_std",
        "reactor_temp_C_slope",
        "meoh_isobutene_ratio_roll_mean",
        "meoh_isobutene_ratio_roll_std",
        "meoh_isobutene_ratio_slope",
    ]


def build_oos_labels(df: pd.DataFrame, horizon_points: int, spec_min: float = MTBE_PURITY_SPEC_MIN) -> pd.Series:
    """Label row t with whether purity is below spec at t + horizon_points.

    Rows too close to the end of the frame (no future value available) are
    dropped by the caller via the returned mask of valid indices (NaN here).
    """
    future_purity = df["mtbe_purity_pct"].shift(-horizon_points)
    label = (future_purity < spec_min).astype("float")
    label[future_purity.isna()] = np.nan
    return label


def chronological_split(n: int, train_frac: float = 0.8) -> tuple[slice, slice]:
    cut = int(n * train_frac)
    return slice(0, cut), slice(cut, n)
