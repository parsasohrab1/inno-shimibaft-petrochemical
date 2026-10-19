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

There is no equivalent official generator for the MEK unit in the SRS —
extending this module to MEK is listed as a TODO in backend/app/seed.py.

Usage:
    python scripts/generate_synthetic_data.py --n-points 5000 --out data/mtbe_synthetic.csv
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def generate_mtbe_synthetic_data(n_points: int = 10_000, freq_min: int = 1, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic data for the MTBE unit, preserving basic physical relations.

    Args:
        n_points: number of time points to generate.
        freq_min: spacing between points, in minutes.
        seed: random seed, for reproducibility.

    Returns:
        A DataFrame with columns: timestamp, reactor_temp_C, reactor_pressure_MPa,
        feed_flow_kg_h, meoh_isobutene_ratio, mtbe_purity_pct, energy_intensity_GJ_t.
    """
    rng = np.random.default_rng(seed)
    time_index = [datetime(2025, 1, 1) + timedelta(minutes=i * freq_min) for i in range(n_points)]

    t = np.linspace(0, 10, n_points)

    # Reactor temperature (74-77 C operating band per SRS tag TI-101, with controlled oscillation)
    reactor_temp = 75.5 + 1.2 * np.sin(0.1 * t) + rng.normal(0, 0.3, n_points)
    reactor_temp = np.clip(reactor_temp, 74.0, 77.0)

    # Reactor pressure (0.69-1.38 MPa per SRS tag PI-102)
    pressure = 1.0 + 0.15 * np.sin(0.05 * t) + rng.normal(0, 0.05, n_points)
    pressure = np.clip(pressure, 0.69, 1.38)

    # Raffinate-1 feed flow (kg/h), with a slight downward drift plus oscillation
    feed_flow = 10_000 - 2 * t + 200 * np.sin(0.2 * t) + rng.normal(0, 100, n_points)
    feed_flow = np.maximum(feed_flow, 3_000)

    # Methanol:isobutylene molar ratio — optimum around 1.1
    meoh_ratio = 1.1 + 0.05 * np.sin(0.15 * t) + rng.normal(0, 0.02, n_points)

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

    return pd.DataFrame({
        "timestamp": time_index,
        "reactor_temp_C": reactor_temp,
        "reactor_pressure_MPa": pressure,
        "feed_flow_kg_h": feed_flow,
        "meoh_isobutene_ratio": meoh_ratio,
        "mtbe_purity_pct": purity,
        "energy_intensity_GJ_t": energy_intensity,
    })


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
