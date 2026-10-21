"""Seed a small amount of clearly-labelled sample data.

Historian ticker: as of the shared digital-twin work
(``backend/app/ml/digital_twin.py``), ALL 10 seeded process tags' demo
``historian_samples`` ticker now come from ONE evolving
``DigitalTwinState`` — stepped once per historian timestamp, so every
tag's value at a given row is read from the SAME internally-consistent
plant-state snapshot, not independently re-randomized per tag. This
replaced an earlier split where only 5 tags (TI-101, PI-102, FI-103,
FI-301, EI-401) came from the physics-informed generator and the other 5
(FI-104, AI-105, TI-201, TI-501, TI-502) were independent
``random.uniform()`` draws — a real bug caught while testing: the
uniform-random ticker routinely disagreed with the physically-coupled
tags (e.g. a feed-flow value that implied a methanol:isobutylene ratio
nothing like the independently-drawn "ratio" the model was actually
trained on). Every row is still tagged ``is_sample = 1``.

The first eight tags (TI-101 ... EI-401) and their normal ranges are taken
verbatim from docs/SRS.md section 3.2.2 (the SRS pushed to this product's
GitHub repo on 1405/06/16, commit f6d8b6d) — these are the client-approved
sample MTBE-unit tag list, not something this scaffold invented. The
remaining MEK-unit tags (TI-501/TI-502) are still this repository's own
placeholders in the sense that no official SRS tag list exists for the
MEK unit — but they are now backed by a real two-stage reaction model
(hydration -> dehydrogenation, see digital_twin.py), not a bare
uniform-random band.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from . import config
from .db import connect, init_db, one
from .ml.digital_twin import DigitalTwinState
from .ml.synthetic import TAG_TO_SYNTHETIC_COLUMN
from .security import hash_password

SEED = 42
random.seed(SEED)

# tag_id, unit, description, measurement_unit, normal_min, normal_max
TAGS = [
    # --- واحد MTBE — از پیوست SRS (بخش ۳.۲.۲)، نه ساخته این اسکلت ---
    ("TI-101", "MTBE", "دمای بستر کاتالیست راکتور MTBE", "°C", 74.0, 77.0),
    ("PI-102", "MTBE", "فشار راکتور MTBE", "MPa", 0.69, 1.38),
    ("FI-103", "MTBE", "دبی خوراک رافینیت ۱", "kg/h", 3000, 10000),
    ("FI-104", "MTBE", "دبی خوراک متانول", "kg/h", 200, 1200),
    ("AI-105", "MTBE", "آنالیز آنلاین ایزوبوتن در خوراک", "%", 30, 55),
    ("TI-201", "MTBE", "دمای برج تقطیر جداسازی MTBE", "°C", 60, 110),
    ("FI-301", "MTBE", "دبی محصول MTBE", "kg/h", 2500, 9500),
    ("EI-401", "MTBE", "مصرف انرژی (بخار/برق) واحد MTBE", "GJ/t", 6.5, 10.5),
    # --- واحد MEK — بدون فهرست تگ رسمی در پیوست SRS؛ اکنون پشتیبانی‌شده
    # توسط یک مدل دومرحله‌ای هیدراتاسیون→دهیدروژناسیون (digital_twin.py) ---
    ("TI-501", "MEK", "دمای واحد هیدراتاسیون بوتن به سک-بوتانول", "°C", 60, 90),
    ("TI-502", "MEK", "دمای دهیدروژناسیون سک-بوتانول به MEK", "°C", 350, 420),
]


def _now_minus(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")


def seed() -> None:
    init_db()
    conn = connect()
    try:
        if one(conn, "SELECT 1 FROM users LIMIT 1"):
            return  # already seeded

        pw = hash_password(config.DEMO_PASSWORD)
        demo_users = [
            ("admin", "مدیر سیستم SPRO", "admin"),
            ("process", "مهندس فرآیند نمونه", "process_engineer"),
            ("energy", "مهندس انرژی و خوراک نمونه", "energy_engineer"),
            ("quality", "مهندس کیفیت نمونه", "quality_engineer"),
        ]
        for username, full_name, role in demo_users:
            conn.execute(
                "INSERT INTO users(username, full_name, role, password_hash, is_active) VALUES (?,?,?,?,1)",
                (username, full_name, role, pw),
            )

        # ALL 10 tags' illustrative "live" ticker now come from ONE stepped
        # DigitalTwinState (backend/app/ml/digital_twin.py) — each of the 60
        # historian timestamps below is ONE snapshot of the whole plant, so
        # every tag's value at that timestamp is mutually consistent (e.g.
        # FI-104's methanol flow at row i is actually derived from FI-103
        # and the reactor state at that SAME row i), not drawn from two
        # unrelated random sources the way the old uniform-random fallback
        # for FI-104/AI-105/TI-201/TI-501/TI-502 was.
        twin = DigitalTwinState(seed=SEED)
        snapshots = [twin.step() for _ in range(60)]

        for tag_id, unit, desc, uom, lo, hi in TAGS:
            conn.execute(
                "INSERT INTO process_tags(tag_id, unit, description, measurement_unit, normal_min, normal_max, source) "
                "VALUES (?,?,?,?,?,?, 'synthetic')",
                (tag_id, unit, desc, uom, lo, hi),
            )
            column = TAG_TO_SYNTHETIC_COLUMN.get(tag_id)
            for i in range(60):
                if column is not None:
                    value = snapshots[i][column]
                else:
                    # Defensive fallback only — unreachable for the 10 tags
                    # above, kept in case a future tag is added without a
                    # twin column (see docs/SRS.md section 9 honesty note).
                    mid = (lo + hi) / 2
                    span = (hi - lo) / 2
                    value = mid + random.uniform(-span, span) * 0.6
                conn.execute(
                    "INSERT INTO historian_samples(tag_id, ts, value, is_sample) VALUES (?,?,?,1)",
                    (tag_id, _now_minus((60 - i) * 15), round(float(value), 3)),
                )

        feed_types = [
            ("C4 Raffinate-1 (mixed C4)", "ایزوبوتیلن ~45%، نرمال‌بوتان و بوتن‌های دیگر"),
            ("Methanol", "خلوص >99.8%"),
            ("n/iso-Butenes (برای MEK)", "بوتن‌های خطی و شاخه‌ای"),
        ]
        for i in range(12):
            feed_type, assay = feed_types[i % len(feed_types)]
            conn.execute(
                "INSERT INTO feed_batches(batch_id, feed_type, quantity_t, quality_assay, received_at, is_sample) "
                "VALUES (?,?,?,?,?,1)",
                (f"FEED-{i+1:04d}", feed_type, round(random.uniform(200, 900), 1), assay, _now_minus((12 - i) * 360)),
            )

        products = ["MTBE", "C4 Raffinate-2", "MEK"]
        for i in range(30):
            product = products[i % len(products)]
            conn.execute(
                "INSERT INTO production_records(product, quantity_t, energy_gj, ts, is_sample) VALUES (?,?,?,?,1)",
                (product, round(random.uniform(20, 120), 1), round(random.uniform(50, 400), 1), _now_minus((30 - i) * 180)),
            )

        lab_specs = [
            ("MTBE", "purity_pct", 97.0, 100.0),
            ("MTBE", "water_ppm", 0.0, 150.0),
            ("MEK", "purity_pct", 99.0, 100.0),
        ]
        for i in range(20):
            product, parameter, spec_min, spec_max = lab_specs[i % len(lab_specs)]
            mid = (spec_min + spec_max) / 2
            span = (spec_max - spec_min) / 2 or 1
            value = mid + random.uniform(-span, span) * 1.1  # occasionally drifts outside spec
            conn.execute(
                "INSERT INTO lab_samples(sample_id, product, parameter, value, spec_min, spec_max, sampled_at, is_sample) "
                "VALUES (?,?,?,?,?,?,?,1)",
                (f"LAB-{i+1:04d}", product, parameter, round(value, 3), spec_min, spec_max, _now_minus((20 - i) * 240)),
            )

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    print("Seeded sample data into", config.DB_PATH)
