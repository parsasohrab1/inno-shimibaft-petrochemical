"""SQLite access layer (scaffold).

A single-file SQLite database is enough for this scaffold and for the
sibling clone projects on this account. If/when SPRO is wired to a real
DCS/Historian/LIMS, ``historian_samples`` and ``lab_samples`` below are the
tables a production-grade time-series/relational store would replace —
keeping the same column names should make that swap mostly mechanical.

All sample rows this scaffold seeds are clearly tagged ``is_sample = 1``
(see ``seed.py``) so real data can never be confused with placeholder data.
"""
import sqlite3
from typing import Any, Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  full_name TEXT,
  role TEXT NOT NULL,
  password_hash TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);

-- Module 1: Process Intelligence & Operating-Condition Optimization
CREATE TABLE IF NOT EXISTS process_tags(
  tag_id TEXT PRIMARY KEY,
  unit TEXT NOT NULL,
  description TEXT,
  measurement_unit TEXT,
  normal_min REAL,
  normal_max REAL,
  source TEXT NOT NULL DEFAULT 'synthetic'
);
CREATE TABLE IF NOT EXISTS historian_samples(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tag_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  value REAL NOT NULL,
  is_sample INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_hist_tag_ts ON historian_samples(tag_id, ts);

-- Module 2: Smart Energy & Feedstock Optimization
CREATE TABLE IF NOT EXISTS feed_batches(
  batch_id TEXT PRIMARY KEY,
  feed_type TEXT NOT NULL,
  quantity_t REAL NOT NULL,
  quality_assay TEXT,
  received_at TEXT NOT NULL,
  is_sample INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS production_records(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product TEXT NOT NULL,
  quantity_t REAL NOT NULL,
  energy_gj REAL,
  ts TEXT NOT NULL,
  is_sample INTEGER NOT NULL DEFAULT 1
);

-- Module 3: Smart Quality Prediction & Off-Spec Detection
CREATE TABLE IF NOT EXISTS lab_samples(
  sample_id TEXT PRIMARY KEY,
  product TEXT NOT NULL,
  parameter TEXT NOT NULL,
  value REAL NOT NULL,
  spec_min REAL,
  spec_max REAL,
  sampled_at TEXT NOT NULL,
  is_sample INTEGER NOT NULL DEFAULT 1
);

-- Module 4: Production Forecasting & Real-Time Operational Decision Support
--
-- ``recommendations`` rows are IMMUTABLE once inserted (NFR-06): their
-- ``status`` column is written once at INSERT time ('pending') and never
-- UPDATEd again. Every operator accept/reject is a NEW row in
-- ``recommendation_decisions`` instead — an append-only audit trail
-- (Khorasan Petrochemical SEM project's advisory-mode pattern on this
-- account). The "current" status of a recommendation is derived by
-- looking at its latest decision row, not stored destructively.
CREATE TABLE IF NOT EXISTS recommendations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  module TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  impact TEXT,
  confidence REAL,
  suggested_action TEXT,   -- JSON: {"parameter": ..., "delta_pct": ...}
  expected_effect TEXT,    -- JSON: {"production_delta_kg_h": ..., "purity_delta_pct": ..., "energy_intensity_delta_pct": ...}
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  is_sample INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS recommendation_decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rec_id INTEGER NOT NULL,
  decision TEXT NOT NULL,   -- 'accepted' | 'rejected'
  actor_username TEXT,
  note TEXT,
  ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_rec_decisions_rec ON recommendation_decisions(rec_id, ts);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return conn.execute(sql, tuple(params)).fetchone()


def rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, tuple(params)).fetchall()


def scalar(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> Any:
    row = one(conn, sql, params)
    return row[0] if row else None
