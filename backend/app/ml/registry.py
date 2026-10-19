"""Lazily loads the trained artifact bundle for the FastAPI services.

Models are trained once (``scripts/train_models.py`` or the background
thread ``main.py`` kicks off on first boot — see ``_ensure_models`` there,
mirroring ``seed.py``'s ``AUTO_SEED`` pattern) and cached on disk under
``config.MODELS_DIR``; this module just loads that bundle into memory
once per process and hands it back, so no request re-trains anything.
"""
from __future__ import annotations

from pathlib import Path

import joblib

from .. import config
from .train import ARTIFACTS_FILENAME, METRICS_FILENAME

_cache: dict[str, dict] = {}


class ModelsNotTrained(RuntimeError):
    pass


def artifacts_path() -> Path:
    return Path(config.MODELS_DIR) / ARTIFACTS_FILENAME


def metrics_path() -> Path:
    return Path(config.MODELS_DIR) / METRICS_FILENAME


def is_ready() -> bool:
    return artifacts_path().exists()


def get_artifacts() -> dict:
    key = str(artifacts_path())
    if key in _cache:
        return _cache[key]
    path = artifacts_path()
    if not path.exists():
        raise ModelsNotTrained(
            "مدل‌ها هنوز آموزش ندیده‌اند — در حال آموزش در پس‌زمینه هستند؛ یا python scripts/train_models.py را اجرا کنید"
        )
    artifacts = joblib.load(path)
    _cache[key] = artifacts
    return artifacts


def clear_cache() -> None:
    _cache.clear()
