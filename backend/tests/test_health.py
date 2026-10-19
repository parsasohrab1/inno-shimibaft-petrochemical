def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["product"] == "SPRO"


def test_auth_required(client):
    assert client.get("/api/process-intelligence/tags").status_code == 401
    bad = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401
