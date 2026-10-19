"""Seed a small amount of clearly-labelled sample data.

This is NOT a physics-informed simulator (unlike the Khorasan Petrochemical
SEM project on this account) — it is just enough illustrative, randomly
generated data for the API and frontend to have something to show while
real DCS/Historian/LIMS integration (see ``services/dcs_ingest.py``) does
not exist yet. Every row is tagged ``is_sample = 1``.

The first eight tags (TI-101 ... EI-401) and their normal ranges are taken
verbatim from docs/SRS.md section 3.2.2 (the SRS pushed to this product's
GitHub repo on 1405/06/16, commit f6d8b6d) — these are the client-approved
sample MTBE-unit tag list, not something this scaffold invented. The
remaining MEK-unit tags are this scaffold's own illustrative placeholders
(the SRS appendix only gives a sample tag list for the MTBE unit), clearly
marked as such below, since Phase 1 also covers the MEK unit but no
official MEK tag list has been provided yet.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from . import config
from .db import connect, init_db, one
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
    # --- واحد MEK — جای‌نگه‌دار این اسکلت (در پیوست SRS فهرست تگ رسمی ندارد) ---
    ("TI-501", "MEK", "دمای واحد هیدراتاسیون بوتن به سک-بوتانول (جای‌نگه‌دار)", "°C", 60, 90),
    ("TI-502", "MEK", "دمای دهیدروژناسیون سک-بوتانول به MEK (جای‌نگه‌دار)", "°C", 350, 420),
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

        for tag_id, unit, desc, uom, lo, hi in TAGS:
            conn.execute(
                "INSERT INTO process_tags(tag_id, unit, description, measurement_unit, normal_min, normal_max, source) "
                "VALUES (?,?,?,?,?,?, 'synthetic')",
                (tag_id, unit, desc, uom, lo, hi),
            )
            # a short illustrative history per tag
            for i in range(60):
                mid = (lo + hi) / 2
                span = (hi - lo) / 2
                value = mid + random.uniform(-span, span) * 0.6
                conn.execute(
                    "INSERT INTO historian_samples(tag_id, ts, value, is_sample) VALUES (?,?,?,1)",
                    (tag_id, _now_minus((60 - i) * 15), round(value, 3)),
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
