"""Central configuration for the SPRO backend.

SPRO (Smart Process, Energy & Production Optimization) is PetroPala Toos'
proposed product for Shimi Baft Petrochemical Company (proposal letter
ref. 14050616001, dated 1405/06/16). This module only reads simple
environment variables with safe local-development defaults; it does not
talk to any real DCS, Historian or LIMS system yet — see
``backend/app/services/dcs_ingest.py`` for the integration stub.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.getenv("DATA_DIR", REPO / "data")).resolve()
DB_PATH = DATA_DIR / "spro.db"
FRONTEND_DIST_DIR = REPO / "frontend" / "dist"

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-please-0123456789")
TOKEN_TTL_MINUTES = int(os.getenv("TOKEN_TTL_MINUTES", "480"))
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo@12345")
AUTO_SEED = os.getenv("AUTO_SEED", "1") == "1"

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")

# Placeholders only — no connection is ever actually attempted in this
# scaffold. Module 1 (process intelligence) would read from these.
DCS_ENDPOINT = os.getenv("DCS_ENDPOINT", "")
HISTORIAN_ENDPOINT = os.getenv("HISTORIAN_ENDPOINT", "")
LAB_LIMS_ENDPOINT = os.getenv("LAB_LIMS_ENDPOINT", "")

DATA_DIR.mkdir(parents=True, exist_ok=True)
