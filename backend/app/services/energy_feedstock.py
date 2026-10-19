"""Module 2 — Smart Energy & Feedstock Optimization.

Implements (as heuristic placeholders — see TODOs) the acceptance criteria
of docs/SRS.md section 3.1.2:
  - FR-M2-01: real-time + cumulative Energy Intensity (energy per tonne
    product, tag EI-401 per SRS 3.2.2);
  - FR-M2-02: flag conditions pushing Energy Intensity above optimal
    (target: detect >= 80% of >5% deviations in pilot testing);
  - FR-M2-03: under feed constraints, propose a production mix between
    MTBE and Raffinate-2 (target: >= 3 scenarios with production/cost);
  - FR-M2-04: a "what-if" simulator for feed ratio / reactor temperature
    (target: UI response < 10 s — see ``forecasting_decision.what_if``,
    which currently implements the linear placeholder for this).

This scaffold computes a simple energy-intensity ratio from the seeded
``production_records`` table and flags records above a fixed multiple of
the sample average — NOT the >=80%-detection-rate deviation flagging
FR-M2-02 asks for. ``recommend_production_mix`` always returns the
highest-tonnage product seen so far and nothing resembling 3 costed
scenarios — it is NOT a real optimizer and does not satisfy FR-M2-03.

TODO (real implementation, needs real plant data and economics):
  - a true energy baseline per ISO 50001-style regression (see the
    Khorasan SEM project's ``energy_perf.py`` for a reference pattern
    already used on this account), not a flat average, to make FR-M2-02's
    detection-rate criterion measurable;
  - an actual constrained optimization (e.g. LP/MILP) over feedstock
    availability, energy limits and product margins, producing >= 3 real
    costed scenarios (FR-M2-03);
  - real feedstock quality assays (rafinate-1 isobutylene content, AI-105)
    feeding the energy-intensity model.
"""
from __future__ import annotations

import sqlite3
import statistics

from ..db import rows


def energy_intensity(conn: sqlite3.Connection) -> dict:
    recs = rows(conn, "SELECT product, quantity_t, energy_gj, ts FROM production_records ORDER BY ts DESC LIMIT 60")
    items = []
    intensities = []
    for r in recs:
        if r["quantity_t"]:
            gj_per_t = r["energy_gj"] / r["quantity_t"]
            intensities.append(gj_per_t)
            items.append({"product": r["product"], "ts": r["ts"], "gj_per_t": round(gj_per_t, 2)})
    if not intensities:
        return {"items": [], "average_gj_per_t": None, "flagged": []}
    avg = statistics.mean(intensities)
    flagged = [i for i in items if i["gj_per_t"] > avg * 1.2]
    return {"items": items, "average_gj_per_t": round(avg, 2), "flagged": flagged,
            "note": "میانگین ساده روی داده نمونه — نه خط پایه رگرسیونی واقعی (ISO 50001)"}


def feed_constraints(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in rows(conn, "SELECT * FROM feed_batches ORDER BY received_at DESC LIMIT 20")]


def recommend_production_mix(conn: sqlite3.Connection) -> dict:
    """Placeholder "optimizer": NOT a real constrained optimization.

    Real implementation would take feedstock availability/quality,
    energy limits and product economics and solve a constrained
    production-mix problem (see the letter's module 2 description).
    """
    best = rows(
        conn,
        "SELECT product, SUM(quantity_t) AS total_t FROM production_records GROUP BY product ORDER BY total_t DESC LIMIT 1",
    )
    product = best[0]["product"] if best else None
    return {
        "recommended_focus_product": product,
        "rationale": "جای‌نگه‌دار: بیشترین حجم تولید در داده نمونه — جایگزین باید با یک مدل بهینه‌سازی محدودیت‌محور واقعی (مثل LP/MILP) روی خوراک، انرژی و اقتصاد محصول باشد",
        "is_placeholder": True,
    }
