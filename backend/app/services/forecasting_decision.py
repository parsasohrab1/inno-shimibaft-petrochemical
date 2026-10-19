"""Module 4 — Production Forecasting & Real-Time Operational Decision Support.

Implements (as heuristic placeholders — see TODOs) the acceptance criteria
of docs/SRS.md section 3.1.4:
  - FR-M4-01: forecast MTBE / Raffinate-2 production rate 1-8 hours ahead
    (target RMSE <= 5% vs. actual);
  - FR-M4-02: real-time recommendations with an explicit "suggested
    action" + "expected effect" (temperature/pressure/flow adjustments);
  - FR-M4-03: rank >= 3 alternative operating scenarios on production,
    quality and energy (multi-criteria scoring).

This scaffold satisfies none of the above. ``outlook`` just sums historical
sample production by product (no time horizon, no RMSE to measure).
``what_if`` is a flat linear percentage applied to a historical total —
NOT a re-simulation of modules 1-3, and nowhere near FR-M4-01's forecast
target. ``list_recommendations``/``add_recommendation`` are plain CRUD with
no "action + expected effect" structure and no ranking logic for FR-M4-03.

TODO (real implementation, needs modules 1-3 to be real first):
  - a genuine 1-8h time-series forecast over process + production
    history, measured against the RMSE <= 5% target (FR-M4-01);
  - what-if scenarios that actually re-run modules 1-3's logic with a
    perturbed input, not a linear percentage estimate (SRS FR-M2-04 /
    FR-M4-03's multi-criteria scenario ranking);
  - recommendation generation with an "action + expected effect" payload,
    wired to real module 1-3 outputs, with an operator accept/reject loop
    and an audit trail (see the Khorasan SEM project's advisory-mode
    pattern on this account for a reference design, and docs/SRS.md
    NFR-06 for the immutable-logging requirement this would need to meet).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..db import rows


def outlook(conn: sqlite3.Connection) -> dict:
    recent = rows(conn, "SELECT product, SUM(quantity_t) AS total_t FROM production_records GROUP BY product")
    return {
        "basis": "جمع ساده تولید نمونه اخیر — نه پیش‌بینی سری‌زمانی واقعی",
        "by_product": [dict(r) for r in recent],
        "is_placeholder": True,
    }


def what_if(conn: sqlite3.Connection, parameter: str, delta_pct: float, note: str | None) -> dict:
    """Linear, naive what-if — NOT a real scenario re-simulation.

    Real implementation would re-evaluate modules 1-3 with the perturbed
    parameter rather than scaling a historical total.
    """
    base = rows(conn, "SELECT SUM(quantity_t) AS total_t FROM production_records")
    base_total = (base[0]["total_t"] or 0.0) if base else 0.0
    estimated = base_total * (1 + delta_pct / 100.0)
    return {
        "parameter": parameter,
        "delta_pct": delta_pct,
        "base_total_t": round(base_total, 1),
        "naive_estimated_total_t": round(estimated, 1),
        "note": note,
        "is_placeholder": True,
        "warning": "برآورد خطی ساده روی داده نمونه؛ جایگزین باید بازاجرای واقعی ماژول‌های ۱ تا ۳ با پارامتر تغییریافته باشد",
    }


def list_recommendations(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in rows(conn, "SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 50")]


def add_recommendation(conn: sqlite3.Connection, module: str, title: str, detail: str, impact: str, confidence: float) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO recommendations(module, title, detail, impact, confidence, status, created_at, is_sample) "
        "VALUES (?,?,?,?,?, 'pending', ?, 1)",
        (module, title, detail, impact, confidence, now),
    )
    conn.commit()
    return cur.lastrowid


def set_recommendation_status(conn: sqlite3.Connection, rec_id: int, status: str) -> None:
    conn.execute("UPDATE recommendations SET status=? WHERE id=?", (status, rec_id))
    conn.commit()
