import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DEMO_PASSWORD", "Demo@12345")
    monkeypatch.setenv("AUTO_SEED", "0")  # seed synchronously below instead

    backend_dir = str(Path(__file__).resolve().parents[1])
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # reload modules so they pick up the patched DATA_DIR
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    from app import config as config_module
    importlib.reload(config_module)
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
