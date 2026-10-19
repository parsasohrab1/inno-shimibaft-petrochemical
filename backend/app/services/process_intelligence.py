"""Module 1 — Process Intelligence & Operating-Condition Optimization.

Implements (as heuristic placeholders — see TODOs) the acceptance criteria
of docs/SRS.md section 3.1.1:
  - FR-M1-01: ingest Historian data (<= 5 min lag, >= 99% tag success);
  - FR-M1-02: optimal operating ranges with a 95% confidence interval for
    key variables (reactor temperature, pressure, MeOH:isobutylene feed
    ratio — tags TI-101, PI-102, FI-103/FI-104/AI-105 per SRS 3.2.2);
  - FR-M1-03: correlate process variables with productivity KPIs
    (>= 5 variables with R^2 >= 0.7).

This scaffold does none of that for real: ``tag_envelope`` only compares
the latest sample against each tag's fixed seeded normal_min/normal_max,
and ``variability_flags`` is a crude relative-stdev threshold — not a
joint, multivariate operating-envelope model, not a confidence interval,
and not a correlation/R^2 analysis.

TODO (real implementation, needs real plant data):
  - replace the fixed normal_min/normal_max band with a data-driven
    operating envelope with a genuine 95% CI (FR-M1-02);
  - joint (multivariate) analysis across correlated tags, not per-tag
    (FR-M1-03), with R^2 reporting against productivity KPIs;
  - wire ``services/dcs_ingest.py`` to a real Historian so FR-M1-01's
    <=5 min lag / >=99% tag-success criteria can actually be measured.
"""
from __future__ import annotations

import sqlite3
import statistics

from ..db import rows


def list_tags(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in rows(conn, "SELECT * FROM process_tags ORDER BY unit, tag_id")]


def tag_envelope(conn: sqlite3.Connection, tag_id: str) -> dict | None:
    """Exact value + range + an illustrative 3-light status for one tag.

    Mirrors the indicator convention used on the other smart-dashboard
    projects on this account: exact value, a range, and a red/yellow/green
    status with a text label (never colour alone) — kept here for
    consistency even though SPRO's own acceptance criteria were not
    specified by the vendor letter.
    """
    tag = rows(conn, "SELECT * FROM process_tags WHERE tag_id=?", (tag_id,))
    if not tag:
        return None
    tag = dict(tag[0])
    samples = rows(conn, "SELECT value, ts FROM historian_samples WHERE tag_id=? ORDER BY ts DESC LIMIT 1", (tag_id,))
    if not samples:
        return {**tag, "value": None, "ts": None, "status": "unknown", "status_label": "بدون داده"}
    value, ts = samples[0]["value"], samples[0]["ts"]
    lo, hi = tag["normal_min"], tag["normal_max"]
    span = (hi - lo) or 1.0
    margin = span * 0.1
    if value < lo - margin or value > hi + margin:
        status, label = "red", "خارج از محدوده مجاز"
    elif value < lo or value > hi:
        status, label = "yellow", "نزدیک به مرز محدوده"
    else:
        status, label = "green", "درون محدوده نرمال"
    return {**tag, "value": value, "ts": ts, "status": status, "status_label": label}


def variability_flags(conn: sqlite3.Connection) -> list[dict]:
    """Flag tags whose recent sample standard deviation looks unusually wide
    relative to their declared normal band — a crude stand-in for the
    letter's "conditions that increase variability or hurt stability".
    """
    flags = []
    for tag in list_tags(conn):
        vals = [r["value"] for r in rows(
            conn, "SELECT value FROM historian_samples WHERE tag_id=? ORDER BY ts DESC LIMIT 30", (tag["tag_id"],)
        )]
        if len(vals) < 5:
            continue
        band = (tag["normal_max"] - tag["normal_min"]) or 1.0
        rel_stdev = statistics.pstdev(vals) / band
        if rel_stdev > 0.25:
            flags.append({
                "tag_id": tag["tag_id"],
                "unit": tag["unit"],
                "relative_variability": round(rel_stdev, 3),
                "note": "نوسان نسبی بالا نسبت به محدوده نرمال تعریف‌شده (آستانه ساده، نه مدل آموزش‌دیده)",
            })
    return flags
