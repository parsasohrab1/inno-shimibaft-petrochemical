"""Synthetic data generator for the MTBE unit.

Adapted (variable names translated, CLI + CSV export added) from the
Python function given verbatim in docs/SRS.md section 3.2.4 — the SRS that
was pushed to this product's GitHub repo README.md on 1405/06/16 (commit
f6d8b6d). That function was reviewed line-by-line before being reused
here: it only uses numpy/pandas to synthesize correlated time series in
memory, with no network or file I/O of its own.

This generates a MTBE-unit-only dataset (reactor temperature, pressure,
feed flow, methanol:isobutylene ratio, MTBE purity, energy intensity) with
simple physically-motivated correlations (e.g. purity degrades the further
temperature and feed ratio drift from their optimum; energy intensity
rises with both). It is NOT validated against the real plant and should
only be used for scaffolding/UI development and for pre-training models
that will later be fine-tuned on real Shimi Baft data (per docs/SRS.md
section 3.2.3).

There is now an equivalent shared physics core for the MEK unit and for
the rest of the MTBE unit's previously-unmodeled tags (FI-104, AI-105,
TI-201) and for Raffinate-2 as a real mass-balance co-product — see
``backend/app/ml/digital_twin.py``. That module deliberately does NOT
touch this file's formulas; it calls ``_mtbe_core`` below (the SAME
numbers this file has always produced) and only ADDS the extra physics on
top, so the line-by-line-reviewed SRS function stays untouched.

NON-FUNCTIONAL REFACTOR (2026-10, digital-twin work): the body of
``generate_mtbe_synthetic_data`` below was extracted into ``_mtbe_core``
(same arrays in, same arrays out) purely so ``digital_twin.py`` can reuse
it for the live-stepping twin without duplicating the formulas. This is
pure code motion — ``test_generator_default_call_unchanged_by_upset_extension``
in backend/tests/test_ml_training.py checks the public function's output
is still bit-for-bit identical.

Usage:
    python scripts/generate_synthetic_data.py --n-points 5000 --out data/mtbe_synthetic.csv
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def _mtbe_core(
    t: np.ndarray,
    rng: np.random.Generator,
    upset_rate: float = 0.0,
    upset_scale: float = 1.0,
) -> dict[str, np.ndarray]:
    """The SRS-sourced MTBE physics, as pure arrays-in/arrays-out.

    Extracted verbatim (no formula changed) from what used to be the body
    of ``generate_mtbe_synthetic_data`` below, so ``backend/app/ml/
    digital_twin.py`` can call the EXACT same formulas for a single
    time-step (``t`` of length 1) as this file uses for a bulk ``n_points``
    array — one physics core, two callers, per the module docstring.

    Args:
        t: the SRS generator's dimensionless time axis (``np.linspace(0,
            10, n_points)`` for bulk use; any 1-D array for stepping use).
        rng: caller-owned RNG (so a stepping caller can keep its own
            persistent stream across calls instead of reseeding each time).
        upset_rate, upset_scale: see generate_mtbe_synthetic_data.

    Returns:
        dict of arrays, same length as ``t``: reactor_temp_C,
        reactor_pressure_MPa, feed_flow_kg_h, meoh_isobutene_ratio,
        mtbe_purity_pct, energy_intensity_GJ_t.
    """
    n_points = len(t)

    # Reactor temperature (74-77 C operating band per SRS tag TI-101, with controlled oscillation)
    reactor_temp = 75.5 + 1.2 * np.sin(0.1 * t) + rng.normal(0, 0.3, n_points)

    # Reactor pressure (0.69-1.38 MPa per SRS tag PI-102)
    pressure = 1.0 + 0.15 * np.sin(0.05 * t) + rng.normal(0, 0.05, n_points)
    pressure = np.clip(pressure, 0.69, 1.38)

    # Raffinate-1 feed flow (kg/h), with a slight downward drift plus oscillation
    feed_flow = 10_000 - 2 * t + 200 * np.sin(0.2 * t) + rng.normal(0, 100, n_points)
    feed_flow = np.maximum(feed_flow, 3_000)

    # Methanol:isobutylene molar ratio — optimum around 1.1
    meoh_ratio = 1.1 + 0.05 * np.sin(0.15 * t) + rng.normal(0, 0.02, n_points)

    if upset_rate > 0:
        # EXTENSION (see docstring): occasional multi-point upset windows
        # pushing temperature and feed ratio further from their setpoints
        # than normal operation ever would, so that enough real OOS events
        # exist to train/evaluate a classifier on. Applied BEFORE clipping
        # reactor_temp, so the same 74-77 clip below still represents the
        # instrument's physical measurement range.
        n_upsets = rng.poisson(upset_rate * n_points)
        for _ in range(n_upsets):
            start = rng.integers(0, n_points)
            width = rng.integers(5, 40)
            end = min(n_points, start + width)
            temp_bump = rng.normal(0, 1.8 * upset_scale)
            ratio_bump = rng.normal(0, 0.12 * upset_scale)
            window = np.hanning(end - start)  # smooth ramp up/down, not a step
            reactor_temp[start:end] += temp_bump * window
            meoh_ratio[start:end] += ratio_bump * window

    reactor_temp = np.clip(reactor_temp, 74.0, 77.0)

    # MTBE purity (%) — degrades with distance from optimal temperature/ratio
    purity = (
        98.5
        - 0.3 * np.abs(reactor_temp - 75.5)
        - 2.0 * np.abs(meoh_ratio - 1.1)
        + rng.normal(0, 0.2, n_points)
    )
    purity = np.clip(purity, 95.0, 99.5)

    # Energy intensity (GJ/t) — rises with temperature excursions and lower purity
    energy_intensity = (
        8.0
        + 0.5 * np.abs(reactor_temp - 75.5)
        + 0.3 * (99.0 - purity)
        + rng.normal(0, 0.1, n_points)
    )

    return {
        "reactor_temp_C": reactor_temp,
        "reactor_pressure_MPa": pressure,
        "feed_flow_kg_h": feed_flow,
        "meoh_isobutene_ratio": meoh_ratio,
        "mtbe_purity_pct": purity,
        "energy_intensity_GJ_t": energy_intensity,
    }


def generate_mtbe_synthetic_data(
    n_points: int = 10_000,
    freq_min: int = 1,
    seed: int = 42,
    upset_rate: float = 0.0,
    upset_scale: float = 1.0,
) -> pd.DataFrame:
    """Generate synthetic data for the MTBE unit, preserving basic physical relations.

    Args:
        n_points: number of time points to generate.
        freq_min: spacing between points, in minutes.
        seed: random seed, for reproducibility.
        upset_rate: EXTENSION beyond the original SRS function (default 0.0
            reproduces the original output exactly, bit-for-bit). When > 0,
            occasional temporary "upset" windows are added to reactor
            temperature and the methanol:isobutylene ratio — e.g. a
            setpoint excursion or a feed-quality hiccup — using the SAME
            downstream purity/energy formulas below. This exists only so
            backend/app/ml/ has enough genuine out-of-spec examples to
            train/evaluate the module-3 OOS classifier on (see
            backend/app/ml/synthetic.py); it does not change the physics
            formula itself, only how far the inputs occasionally wander.
        upset_scale: amplitude multiplier for upset windows (only matters
            when upset_rate > 0).

    Returns:
        A DataFrame with columns: timestamp, reactor_temp_C, reactor_pressure_MPa,
        feed_flow_kg_h, meoh_isobutene_ratio, mtbe_purity_pct, energy_intensity_GJ_t.
    """
    rng = np.random.default_rng(seed)
    time_index = [datetime(2025, 1, 1) + timedelta(minutes=i * freq_min) for i in range(n_points)]
    t = np.linspace(0, 10, n_points)

    core = _mtbe_core(t, rng, upset_rate=upset_rate, upset_scale=upset_scale)

    return pd.DataFrame({"timestamp": time_index, **core})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-points", type=int, default=5_000)
    parser.add_argument("--freq-min", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=None, help="CSV output path; prints a preview if omitted")
    args = parser.parse_args()

    df = generate_mtbe_synthetic_data(n_points=args.n_points, freq_min=args.freq_min, seed=args.seed)
    if args.out:
        df.to_csv(args.out, index=False)
        print(f"Wrote {len(df)} rows to {args.out}")
    else:
        print(df.head())


if __name__ == "__main__":
    main()
