"""Shared physics-informed digital-twin core for ALL process streams
(MTBE unit, Raffinate-2 as its mass-balance co-product, and the MEK unit).

Architecture (mirrors the Khorasan Petrochemical SEM project's
``src/sems/simulator.py`` on this account): ONE module holding the
physics, used both to generate the synthetic TRAINING dataset
(``generate_twin_frame`` below, called from
``backend/app/ml/synthetic.py``) and to drive a LIVE, stepping twin state
(``DigitalTwinState`` below, called from ``backend/app/seed.py`` to build
the demo historian ticker). Both callers run the exact same formulas —
vectorized over an array for bulk generation, or on a length-1 array per
``.step()`` call for live use — so a bulk-trained model's envelope and a
live snapshot describe the same plant, not two independently-randomized
stand-ins.

Relationship to ``scripts/generate_synthetic_data.py``: this module does
NOT re-derive or duplicate the MTBE core (reactor temperature, pressure,
Raffinate-1 feed flow, methanol:isobutylene ratio, MTBE purity, energy
intensity) — that function was adapted line-by-line from docs/SRS.md and
must stay untouched. Instead, this module calls its extracted
``_mtbe_core`` helper and ADDS everything the SRS generator does not
cover:
  - FI-104 (methanol feed), AI-105 (isobutene feed %), TI-201
    (distillation temperature) for the MTBE unit — previously independent
    ``random.uniform()`` draws in backend/app/seed.py, now derived from
    the SAME reactor state and feed-quality disturbance.
  - Raffinate-2 and the MTBE product flow (FI-301) as a REAL mass-balance
    co-product of the reaction (isobutene + methanol -> MTBE; unreacted
    isobutene + the rest of the C4 feed -> Raffinate-2), replacing the old
    engineered proxy ``feed_flow_kg_h * purity/100``.
  - The MEK unit's two reaction stages named in backend/app/seed.py's tag
    docstrings: hydration of linear/iso-butenes to sec-butanol (TI-501),
    then dehydrogenation of sec-butanol to MEK (TI-502).

APPROXIMATIONS — read before extending (same framing as the Khorasan
project's simulator.py; this is first-order mass/energy balance, NOT an
Aspen HYSYS/Plus-level process simulation):
  - All "conversion efficiency peaks near an optimum temperature" curves
    below are simple linear-distance-from-optimum models, the same shape
    the SRS-sourced MTBE purity formula already uses — not a real
    Arrhenius/kinetic rate model with activation energies.
  - The MEK unit's physics (feed flow, TI-501/TI-502 optimum points,
    conversion-vs-temperature coefficients, MEK-unit energy intensity) are
    THIS REPOSITORY'S OWN engineering assumptions, inferred only from the
    tag docstrings already in backend/app/seed.py (which themselves say
    the MEK tags are "جای‌نگه‌دار" — placeholders, since the SRS appendix
    gives no official MEK tag list or kinetics). They are NOT vendor-
    confirmed kinetics, NOT validated against Shimi Baft's real MEK unit,
    and should be replaced the moment real data or a vendor datasheet is
    available.
  - Mass balances use real molar masses (stoichiometry), but water
    consumption in the hydration stage and hydrogen co-production in the
    dehydrogenation stage are not tracked as separate streams — only the
    organic product masses are carried through.
  - AI-105 (feed isobutene content) and the MEK unit's butene feed flow
    are modelled as independent slowly-varying upstream disturbances (no
    real upstream FCC/dehydrogenation-unit model feeds them), the same
    simplification the Khorasan project's ``sample_disturbances`` uses
    for feed composition.

Nothing here is trained or validated on real Shimi Baft plant data — see
backend/app/ml/__init__.py and docs/SRS.md section 9.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .synthetic import _mtbe_core

# --- Stoichiometry (real molar masses, kg/kmol) ----------------------------
ISOBUTYLENE_MW = 56.1
METHANOL_MW = 32.0
BUTENE_MW = 56.1  # linear/iso-butenes feeding the MEK route, same formula C4H8
SEC_BUTANOL_MW = 74.1  # C4H10O (butene + water, mass-conserving: 56.1 + 18.0 ~= 74.1)
MEK_MW = 72.1  # C4H8O

# tag_id -> dataframe column, for the tags this module adds on top of the
# SRS-sourced MTBE core. See backend/app/ml/synthetic.py's
# TAG_TO_SYNTHETIC_COLUMN for the merged, authoritative mapping.
EXTENSION_TAG_TO_COLUMN = {
    "FI-104": "methanol_feed_kg_h",
    "AI-105": "isobutene_feed_pct",
    "TI-201": "distillation_temp_C",
    "TI-501": "hydration_temp_C",
    "TI-502": "dehydrogenation_temp_C",
}


def compute_mtbe_extension(
    reactor_temp_C: np.ndarray,
    reactor_pressure_MPa: np.ndarray,
    feed_flow_kg_h: np.ndarray,
    meoh_isobutene_ratio: np.ndarray,
    t: np.ndarray,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    """FI-104, AI-105, TI-201 + the real Raffinate-2/MTBE mass balance.

    All inputs/outputs are arrays of the same length as ``t`` (length 1
    for a single live step, length n_points for bulk training-frame
    generation) — see the module docstring for why this one function
    serves both callers.
    """
    n = len(t)

    # AI-105: isobutene content of the Raffinate-1 feed (%) — an upstream
    # feed-quality disturbance, not controlled by the MTBE reactor itself
    # (APPROX: no real upstream FCC/dehydrogenation unit is modelled).
    isobutene_feed_pct = np.clip(
        42.0 + 6.0 * np.sin(0.07 * t) + rng.normal(0, 1.5, n), 30.0, 55.0
    )

    isobutene_feed_kg_h = feed_flow_kg_h * isobutene_feed_pct / 100.0
    isobutene_feed_kmol_h = isobutene_feed_kg_h / ISOBUTYLENE_MW

    # FI-104: methanol feed — derived so the already-driving molar ratio
    # (meoh_isobutene_ratio, from the SRS-sourced MTBE core) is actually
    # realized by a real feed-flow tag, plus small metering noise. This
    # REPLACES the independent random.uniform() draw backend/app/seed.py
    # used before.
    methanol_feed_kmol_h = isobutene_feed_kmol_h * meoh_isobutene_ratio
    methanol_feed_kg_h = np.clip(
        methanol_feed_kmol_h * METHANOL_MW * (1.0 + rng.normal(0, 0.01, n)), 50.0, 2000.0
    )

    # Isobutene -> MTBE conversion efficiency (%) — same linear-distance-
    # from-optimum shape as the SRS purity formula, but a distinct
    # quantity (fraction of isobutene actually reacted, not product
    # purity).
    isobutene_conversion_pct = np.clip(
        97.0
        - 0.5 * np.abs(reactor_temp_C - 75.5)
        - 3.0 * np.abs(meoh_isobutene_ratio - 1.1)
        + rng.normal(0, 0.3, n),
        85.0, 99.0,
    )
    isobutene_reacted_kg_h = isobutene_feed_kg_h * isobutene_conversion_pct / 100.0
    # 1:1 molar reaction (isobutylene + methanol -> MTBE): the methanol
    # mass that reacts is stoichiometrically tied to the isobutene reacted.
    methanol_reacted_kg_h = isobutene_reacted_kg_h * (METHANOL_MW / ISOBUTYLENE_MW)

    # FI-301 (MTBE product flow), as a REAL mass-balance sum of the two
    # reacted feed streams — replaces the old engineered proxy
    # (feed_flow_kg_h * purity/100) backend/app/ml/synthetic.py used.
    mtbe_mass_balance_kg_h = isobutene_reacted_kg_h + methanol_reacted_kg_h

    # Raffinate-2: the unreacted part of the C4 (Raffinate-1) feed — a
    # real mass-balance co-product, not a bolted-on proxy.
    raffinate2_kg_h = np.maximum(feed_flow_kg_h - isobutene_reacted_kg_h, 0.0)

    # TI-201: distillation column temperature separating MTBE from
    # unreacted C4s/excess methanol. APPROX: modelled as rising with
    # operating pressure (higher boiling points) and with the extra
    # reboil duty needed when conversion is low (more unreacted light
    # ends to strip out) — first-order, not a real tray-by-tray model.
    distillation_temp_C = np.clip(
        70.0
        + 25.0 * (reactor_pressure_MPa - 0.69) / (1.38 - 0.69)
        + 0.4 * (97.0 - isobutene_conversion_pct)
        + rng.normal(0, 1.0, n),
        60.0, 110.0,
    )

    return {
        "isobutene_feed_pct": isobutene_feed_pct,
        "methanol_feed_kg_h": methanol_feed_kg_h,
        "isobutene_conversion_pct": isobutene_conversion_pct,
        # kept under both names: "mtbe_mass_balance_kg_h" for readability
        # in this module/tests, "product_flow_kg_h" because that is the
        # column backend/app/ml/synthetic.py's TAG_TO_SYNTHETIC_COLUMN maps
        # FI-301 to (so a single DigitalTwinState.step() snapshot already
        # has the tag-ready key, with no separate rename step needed).
        "mtbe_mass_balance_kg_h": mtbe_mass_balance_kg_h,
        "product_flow_kg_h": mtbe_mass_balance_kg_h,
        "raffinate2_kg_h": raffinate2_kg_h,
        "distillation_temp_C": distillation_temp_C,
    }


def compute_mek_unit(t: np.ndarray, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """The MEK unit's two reaction stages (see module docstring's honesty
    note: these coefficients are this repository's own illustrative
    engineering assumptions, not vendor-confirmed kinetics).

      Stage 1 — hydration: linear/iso-butenes + water -> sec-butanol (TI-501)
      Stage 2 — dehydrogenation: sec-butanol -> MEK + H2 (TI-502)
    """
    n = len(t)

    # Upstream feed flow of linear/iso-butenes to the hydration stage — no
    # official SRS tag exists for this yet (APPROX: independent bounded
    # disturbance, same simplification used for the MTBE unit's feed).
    butene_feed_kg_h = np.clip(
        2500.0 + 300.0 * np.sin(0.08 * t) + rng.normal(0, 80.0, n), 1500.0, 4000.0
    )

    # TI-501: hydration reactor temperature, band 60-90 C (backend/app/seed.py),
    # illustrative optimum ~72 C.
    hydration_temp_C = np.clip(
        72.0 + 6.0 * np.sin(0.09 * t + 1.0) + rng.normal(0, 1.0, n), 60.0, 90.0
    )
    hydration_conversion_pct = np.clip(
        90.0 - 0.6 * np.abs(hydration_temp_C - 72.0) + rng.normal(0, 0.6, n), 70.0, 94.0
    )
    butene_reacted_kg_h = butene_feed_kg_h * hydration_conversion_pct / 100.0
    secbutanol_kg_h = butene_reacted_kg_h * (SEC_BUTANOL_MW / BUTENE_MW)

    # TI-502: dehydrogenation reactor temperature, band 350-420 C, optimum ~385 C.
    dehydrogenation_temp_C = np.clip(
        385.0 + 10.0 * np.sin(0.06 * t + 2.0) + rng.normal(0, 2.0, n), 350.0, 420.0
    )
    dehydrogenation_conversion_pct = np.clip(
        88.0 - 0.5 * np.abs(dehydrogenation_temp_C - 385.0) + rng.normal(0, 0.8, n), 65.0, 92.0
    )
    mek_production_kg_h = secbutanol_kg_h * dehydrogenation_conversion_pct / 100.0 * (MEK_MW / SEC_BUTANOL_MW)

    # MEK purity (%, lab) — degrades with distance from either stage's
    # optimum (unreacted sec-butanol/side-product carryover); matches
    # backend/app/seed.py's MEK purity_pct spec_min=99.0.
    mek_purity_pct = np.clip(
        99.4
        - 0.04 * np.abs(dehydrogenation_temp_C - 385.0)
        - 0.03 * np.abs(hydration_temp_C - 72.0)
        + rng.normal(0, 0.15, n),
        97.0, 99.9,
    )

    # Overall MEK-unit energy intensity (GJ/t MEK) — two reaction stages +
    # separation, additive first-order model (illustrative coefficients).
    mek_energy_intensity_GJ_t = (
        9.0
        + 0.04 * np.abs(hydration_temp_C - 72.0)
        + 0.03 * np.abs(dehydrogenation_temp_C - 385.0)
        + 0.2 * (100.0 - dehydrogenation_conversion_pct)
        + rng.normal(0, 0.2, n)
    )

    return {
        "hydration_temp_C": hydration_temp_C,
        "dehydrogenation_temp_C": dehydrogenation_temp_C,
        "mek_butene_feed_kg_h": butene_feed_kg_h,
        "hydration_conversion_pct": hydration_conversion_pct,
        "secbutanol_kg_h": secbutanol_kg_h,
        "dehydrogenation_conversion_pct": dehydrogenation_conversion_pct,
        "mek_production_kg_h": mek_production_kg_h,
        "mek_purity_pct": mek_purity_pct,
        "mek_energy_intensity_GJ_t": mek_energy_intensity_GJ_t,
    }


def generate_twin_frame(
    n_points: int = 20_000,
    freq_min: int = 1,
    seed: int = 42,
    upset_rate: float = 0.0,
    upset_scale: float = 1.0,
) -> pd.DataFrame:
    """Bulk/vectorized form of the shared twin — the MTBE core (untouched
    SRS formulas) plus this module's MTBE extension and MEK unit, all in
    one DataFrame with a consistent row-by-row (i.e. consistent-in-time)
    relationship between every column.

    The extension/MEK physics use a SEPARATE rng stream, seeded off the
    same top-level ``seed`` (offset so it never consumes the MTBE core's
    own draws and therefore never changes its bit-for-bit output — see
    scripts/generate_synthetic_data.py's docstring and the test that
    checks this).
    """
    core_rng = np.random.default_rng(seed)
    t = np.linspace(0, 10, n_points)
    core = _mtbe_core(t, core_rng, upset_rate=upset_rate, upset_scale=upset_scale)

    ext_rng = np.random.default_rng(seed + 1_000_003)
    extension = compute_mtbe_extension(
        core["reactor_temp_C"], core["reactor_pressure_MPa"], core["feed_flow_kg_h"],
        core["meoh_isobutene_ratio"], t, ext_rng,
    )
    mek = compute_mek_unit(t, ext_rng)

    return pd.DataFrame({**core, **extension, **mek})


@dataclass
class DigitalTwinState:
    """A small, genuinely stateful stepper over the exact same physics as
    ``generate_twin_frame`` — one ``.step()`` call advances the whole
    multi-unit plant by one tick and returns ONE internally-consistent
    snapshot (every tag's value in that snapshot was derived from the
    SAME reactor/feed state, never redrawn independently per tag).

    Used by backend/app/seed.py to build the demo historian ticker for
    ALL tags (replacing the old mix of "5 tags from one generator, 5 tags
    from independent random.uniform() calls"). Kept small and dependency-
    free enough that a future always-on live loop (mirroring the Khorasan
    project's background ``LiveSimulator``) could call ``.step()`` on a
    timer without any redesign.
    """

    seed: int = 42
    dt_t: float = 0.05  # per-step increment of the SRS generator's dimensionless time axis
    t: float = field(default=0.0, init=False)
    step_count: int = field(default=0, init=False)
    _core_rng: np.random.Generator = field(init=False, repr=False)
    _ext_rng: np.random.Generator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._core_rng = np.random.default_rng(self.seed)
        self._ext_rng = np.random.default_rng(self.seed + 1_000_003)

    def step(self) -> dict[str, float]:
        """Advance by one tick; return a flat dict of every modelled
        quantity (MTBE core + extension + MEK unit) at that tick, all
        mutually consistent.
        """
        t_arr = np.array([self.t])
        core = _mtbe_core(t_arr, self._core_rng, upset_rate=0.0, upset_scale=1.0)
        extension = compute_mtbe_extension(
            core["reactor_temp_C"], core["reactor_pressure_MPa"], core["feed_flow_kg_h"],
            core["meoh_isobutene_ratio"], t_arr, self._ext_rng,
        )
        mek = compute_mek_unit(t_arr, self._ext_rng)

        snapshot = {k: float(v[0]) for k, v in {**core, **extension, **mek}.items()}
        snapshot["t"] = self.t
        snapshot["step"] = self.step_count

        self.t += self.dt_t
        self.step_count += 1
        return snapshot
