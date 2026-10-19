def H(tokens, role="admin"):
    return tokens[role]


def test_module1_process_intelligence(client, tokens):
    tags = client.get("/api/process-intelligence/tags", headers=H(tokens)).json()
    assert len(tags) == 10
    tag_id = tags[0]["tag_id"]
    envelope = client.get(f"/api/process-intelligence/tags/{tag_id}/envelope", headers=H(tokens)).json()
    assert envelope["status"] in ("red", "yellow", "green", "unknown")
    assert client.get("/api/process-intelligence/tags/NOPE/envelope", headers=H(tokens)).status_code == 404
    flags = client.get("/api/process-intelligence/variability-flags", headers=H(tokens)).json()
    assert isinstance(flags, list)


def test_module2_energy_feedstock(client, tokens):
    intensity = client.get("/api/energy-feedstock/intensity", headers=H(tokens)).json()
    assert "average_gj_per_t" in intensity
    batches = client.get("/api/energy-feedstock/feed-batches", headers=H(tokens)).json()
    assert len(batches) == 12
    mix = client.post("/api/energy-feedstock/optimize-mix", headers=H(tokens)).json()
    assert mix["is_placeholder"] is True


def test_module3_quality_prediction(client, tokens):
    risk = client.get("/api/quality/offspec-risk", headers=H(tokens)).json()
    assert len(risk) > 0
    assert all(0 <= r["offspec_risk_0_1"] <= 1 for r in risk)


def test_module4_forecasting_decision(client, tokens):
    outlook = client.get("/api/forecast/outlook", headers=H(tokens)).json()
    assert outlook["is_placeholder"] is True
    what_if = client.post(
        "/api/forecast/what-if", json={"parameter": "feed_rate", "delta_pct": 5}, headers=H(tokens)
    ).json()
    assert what_if["delta_pct"] == 5
    recs = client.get("/api/forecast/recommendations", headers=H(tokens)).json()
    assert recs == []  # scaffold seeds no recommendations yet
