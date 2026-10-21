"""Module 1 training — real operating envelopes + multivariate R^2.

Implements the two measurable pieces of docs/SRS.md FR-M1 that do not
need a live DCS/Historian connection (FR-M1-01 genuinely does, and stays
``NotImplementedError`` in services/dcs_ingest.py):

  FR-M1-02: a data-driven operating envelope per key tag, with a genuine
  95% confidence interval — not the fixed seeded normal_min/normal_max
  band the old scaffold used. Two different "95%" numbers are reported
  together, because the SRS phrase is ambiguous and both readings are
  useful:
    - ``ci95_of_mean``: the classic 95% CI on the *mean* (t-distribution),
      i.e. how precisely we know the central tendency.
    - ``operating_band_p2_5_97_5``: the 2.5th-97.5th percentile band of
      the data itself, i.e. the "normal operating envelope" an engineer
      would actually compare a live reading against.

  FR-M1-03: multivariate correlation between >=5 process variables and a
  productivity KPI, reporting R^2, via a linear regression trained on an
  80/20 chronological split (see docs/SRS.md section 4 for the 80/20
  cross-validation requirement).

Honesty note on the KPI: FI-301 (``product_flow_kg_h``) is now a REAL
mass-balance co-product computed by the shared digital-twin core
(``backend/app/ml/digital_twin.py``) rather than the old engineered
proxy ``feed_flow_kg_h * (mtbe_purity_pct / 100)``. Because
``feed_flow_kg_h`` is both one of the 5 regressors here AND a direct
input to that mass balance (isobutene fed -> isobutene reacted -> product
mass), this measured R^2 is still somewhat inflated relative to what an
independently-measured FI-301 tag would give — the mass balance is a
real physical relationship (not a tautology), it is just not independent
evidence of the *other* 4 regressors' predictive value on their own. The
API response and docs/SRS.md say this plainly rather than presenting the
number as if FI-301 were an independently-measured tag.

``train_mek_productivity_correlation`` below is the analogous FR-M1-03
analysis for the MEK unit (added with the digital-twin work): it
correlates the MEK unit's own process variables against real MEK
production (also a mass-balance quantity, from the two-stage
hydration/dehydrogenation model in digital_twin.py), reported as a
SEPARATE regression rather than mixed into the MTBE one, because the two
units' feeds/products are physically unrelated quantities.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from .synthetic import TAG_TO_SYNTHETIC_COLUMN, chronological_split

CORRELATION_FEATURES = [
    "reactor_temp_C",
    "reactor_pressure_MPa",
    "feed_flow_kg_h",
    "meoh_isobutene_ratio",
    "energy_intensity_GJ_t",
    # AI-105 — added with the digital-twin work: FI-301 is now a REAL mass
    # balance driven directly by the feed's isobutene content, so leaving
    # this out (as the pre-twin proxy-based version of this list did)
    # starves the regression of one of the new target's actual causal
    # inputs and tanks R^2 for no physical reason — not because the
    # relationship got weaker, but because a real driver was omitted.
    "isobutene_feed_pct",
]
PRODUCTIVITY_TARGET = "product_flow_kg_h"

# FR-M1-03 for the MEK unit — see module docstring.
MEK_CORRELATION_FEATURES = [
    "hydration_temp_C",
    "dehydrogenation_temp_C",
    "mek_butene_feed_kg_h",
    "hydration_conversion_pct",
    "dehydrogenation_conversion_pct",
]
MEK_PRODUCTIVITY_TARGET = "mek_production_kg_h"


@dataclass
class TagEnvelope:
    tag_id: str
    column: str
    n: int
    mean: float
    std: float
    ci95_of_mean: tuple[float, float]
    operating_band_p2_5_97_5: tuple[float, float]


@dataclass
class ProductivityCorrelation:
    target: str
    features: list[str]
    coefficients: dict[str, float]
    intercept: float
    r2_train: float
    r2_test: float
    n_train: int
    n_test: int
    meets_target: bool = field(init=False)

    def __post_init__(self):
        self.meets_target = self.r2_test >= 0.7


def compute_operating_envelopes(df) -> dict[str, TagEnvelope]:
    out: dict[str, TagEnvelope] = {}
    for tag_id, column in TAG_TO_SYNTHETIC_COLUMN.items():
        values = df[column].to_numpy()
        n = len(values)
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1))
        if n > 1 and std > 0:
            ci_lo, ci_hi = stats.t.interval(0.95, df=n - 1, loc=mean, scale=std / np.sqrt(n))
        else:
            ci_lo, ci_hi = mean, mean
        p_lo, p_hi = np.percentile(values, [2.5, 97.5])
        out[tag_id] = TagEnvelope(
            tag_id=tag_id,
            column=column,
            n=n,
            mean=round(mean, 4),
            std=round(std, 4),
            ci95_of_mean=(round(float(ci_lo), 4), round(float(ci_hi), 4)),
            operating_band_p2_5_97_5=(round(float(p_lo), 4), round(float(p_hi), 4)),
        )
    return out


def _train_correlation(df, features: list[str], target: str) -> ProductivityCorrelation:
    train_idx, test_idx = chronological_split(len(df))
    X = df[features].to_numpy()
    y = df[target].to_numpy()
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    model = LinearRegression()
    model.fit(X_train, y_train)
    r2_train = r2_score(y_train, model.predict(X_train))
    r2_test = r2_score(y_test, model.predict(X_test))

    return ProductivityCorrelation(
        target=target,
        features=list(features),
        coefficients={f: round(float(c), 6) for f, c in zip(features, model.coef_)},
        intercept=round(float(model.intercept_), 6),
        r2_train=round(float(r2_train), 4),
        r2_test=round(float(r2_test), 4),
        n_train=int(train_idx.stop - (train_idx.start or 0)),
        n_test=int(len(df) - (test_idx.start or 0)),
    )


def train_productivity_correlation(df) -> ProductivityCorrelation:
    """FR-M1-03 for the MTBE unit — see module docstring's honesty note."""
    return _train_correlation(df, CORRELATION_FEATURES, PRODUCTIVITY_TARGET)


def train_mek_productivity_correlation(df) -> ProductivityCorrelation:
    """FR-M1-03 for the MEK unit — see module docstring."""
    return _train_correlation(df, MEK_CORRELATION_FEATURES, MEK_PRODUCTIVITY_TARGET)
