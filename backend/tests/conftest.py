import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def trained_models_dir(tmp_path_factory):
    """Train once, small, for the whole test session.

    Real per-test training would be far too slow (tens of seconds each);
    MODELS_DIR is intentionally decoupled from DATA_DIR (see
    backend/app/config.py) so this can be shared across every test's
    otherwise-isolated DB, while still exercising the real training code
    path (small synthetic dataset, same functions production training
    uses) rather than mocking it out.
    """
    backend_dir = str(Path(__file__).resolve().parents[1])
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from app.ml.train import train_all

    out_dir = tmp_path_factory.mktemp("models")
    train_all(out_dir=out_dir, n_points=3000, seed=1, upset_rate=0.02, upset_scale=3.5)
    return out_dir


@pytest.fixture()
def client(tmp_path, monkeypatch, trained_models_dir):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODELS_DIR", str(trained_models_dir))
    monkeypatch.setenv("AUTO_TRAIN_MODELS", "0")  # already trained above; don't retrain per test
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DEMO_PASSWORD", "Demo@12345")
    monkeypatch.setenv("AUTO_SEED", "0")  # seed synchronously below instead

    backend_dir = str(Path(__file__).resolve().parents[1])
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # reload modules so they pick up the patched DATA_DIR/MODELS_DIR
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    from app import config as config_module
    importlib.reload(config_module)
    from app.ml import registry as registry_module
    registry_module.clear_cache()
    from app.seed import seed
    seed()

    from app.main import app as fastapi_app
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture()
def tokens(client):
    out = {}
    for username in ("admin", "process", "energy", "quality"):
        r = client.post("/api/auth/login", json={"username": username, "password": "Demo@12345"})
        assert r.status_code == 200, r.text
        out[{"admin": "admin", "process": "process_engineer", "energy": "energy_engineer", "quality": "quality_engineer"}[username]] = \
            {"Authorization": f"Bearer {r.json()['access_token']}"}
    out["admin"] = out.get("admin") or out["admin"]
    return out
