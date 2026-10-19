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


def test_module1_tag_envelope_uses_trained_model_for_modelled_tags(client, tokens):
    """TI-101 is one of the 5 tags backend/app/ml/synthetic.py models — its
    envelope should come from the trained model (basis='model'), not the
    fixed seeded band."""
    envelope = client.get("/api/process-intelligence/tags/TI-101/envelope", headers=H(tokens)).json()
    assert envelope["basis"] == "model"
    assert "ci95_of_mean" in envelope
    assert "operating_band_p2_5_97_5" in envelope

    # TI-501 is a MEK placeholder tag the generator never modelled
    not_modeled = client.get("/api/process-intelligence/tags/TI-501/envelope", headers=H(tokens)).json()
    assert not_modeled["basis"] == "not_modeled"


def test_module1_operating_envelopes_and_correlation(client, tokens):
    envelopes = client.get("/api/process-intelligence/operating-envelopes", headers=H(tokens)).json()
    assert envelopes["ready"] is True
    assert "TI-101" in envelopes["tags"]
    assert envelopes["tags"]["TI-101"]["ci95_of_mean"][0] <= envelopes["tags"]["TI-101"]["mean"]

    corr = client.get("/api/process-intelligence/productivity-correlation", headers=H(tokens)).json()
    assert corr["ready"] is True
    assert len(corr["features"]) >= 5  # FR-M1-03's >= 5 variables
    assert "r2_test" in corr
    assert 0.0 <= corr["r2_test"] <= 1.0


def test_module2_energy_feedstock(client, tokens):
    intensity = client.get("/api/energy-feedstock/intensity", headers=H(tokens)).json()
    assert "average_gj_per_t" in intensity
    assert intensity["energy_baseline"]["ready"] is True
    assert "deviation_detection" in intensity["energy_baseline"]

    batches = client.get("/api/energy-feedstock/feed-batches", headers=H(tokens)).json()
    assert len(batches) == 12

    mix = client.post("/api/energy-feedstock/optimize-mix", headers=H(tokens)).json()
    assert mix["is_placeholder"] is False
    assert len(mix["scenarios"]) >= 3  # FR-M2-03's >= 3 costed scenarios
    for s in mix["scenarios"]:
        assert "profit_usd" in s and "production_t" in s


def test_module3_quality_prediction(client, tokens):
    risk = client.get("/api/quality/offspec-risk", headers=H(tokens)).json()
    assert len(risk) > 0
    assert all(0 <= r["offspec_risk_0_1"] <= 1 for r in risk)

    pred = client.get("/api/quality/model-predictions", headers=H(tokens)).json()
    assert pred["ready"] is True
    assert "predicted_purity_pct" in pred
    assert 90.0 <= pred["predicted_purity_pct"] <= 100.0
    assert "oos_30min_probability" in pred
    assert 0.0 <= pred["oos_30min_probability"] <= 1.0
    assert len(pred["contributing_factors"]) >= 3  # FR-M3-03's >= 3 ranked factors


def test_module4_forecasting_decision(client, tokens):
    outlook = client.get("/api/forecast/outlook", headers=H(tokens)).json()
    assert outlook["is_placeholder"] is False
    assert outlook["ready"] is True
    assert "1" in {str(k) for k in outlook["forecast_kg_h_by_horizon_h"]} or 1 in outlook["forecast_kg_h_by_horizon_h"]

    what_if = client.post(
        "/api/forecast/what-if", json={"parameter": "reactor_temp_C", "delta_pct": 1.0}, headers=H(tokens)
    ).json()
    assert what_if["is_placeholder"] is False
    assert "baseline" in what_if and "scenario" in what_if
    assert "predicted_purity_pct" in what_if["baseline"]

    scenarios = client.get("/api/forecast/scenarios", headers=H(tokens)).json()
    assert scenarios["ready"] is True
    assert len(scenarios["scenarios"]) >= 3  # FR-M4-03's >= 3 scenarios

    recs = client.get("/api/forecast/recommendations", headers=H(tokens)).json()
    assert recs == []  # scaffold seeds no recommendations yet


def test_module4_what_if_rejects_unknown_parameter(client, tokens):
    result = client.post(
        "/api/forecast/what-if", json={"parameter": "not_a_real_tag", "delta_pct": 5}, headers=H(tokens)
    ).json()
    assert "error" in result


def test_module4_recommendation_audit_trail_is_append_only(client, tokens):
    created = client.post(
        "/api/forecast/recommendations",
        json={
            "module": "quality_prediction",
            "title": "تست",
            "detail": "جزئیات تست",
            "impact": "quality",
            "confidence": 0.5,
            "suggested_action": {"parameter": "reactor_temp_C", "delta_pct": -1.0},
            "expected_effect": {"purity_delta_pct": 0.1},
        },
        headers=H(tokens),
    ).json()
    rec_id = created["id"]

    accept = client.post(
        f"/api/forecast/recommendations/{rec_id}/status", json={"status": "accepted", "note": "تایید شد"}, headers=H(tokens)
    )
    assert accept.status_code == 200

    # a second, DIFFERENT decision must be appended, not overwrite the first
    reject = client.post(
        f"/api/forecast/recommendations/{rec_id}/status", json={"status": "rejected", "note": "نظر عوض شد"}, headers=H(tokens)
    )
    assert reject.status_code == 200

    recs = client.get("/api/forecast/recommendations", headers=H(tokens)).json()
    rec = next(r for r in recs if r["id"] == rec_id)
    assert rec["status"] == "pending"  # the ORIGINAL row's status column is never mutated
    assert rec["suggested_action"] == {"parameter": "reactor_temp_C", "delta_pct": -1.0}
    assert len(rec["decisions"]) == 2  # both decisions kept, append-only
    assert rec["decisions"][0]["decision"] == "accepted"
    assert rec["decisions"][1]["decision"] == "rejected"
    assert rec["effective_status"] == "rejected"  # the LATEST decision, derived, not stored destructively


def test_module4_auto_generate_recommendation_shape(client, tokens):
    result = client.post("/api/forecast/recommendations/auto-generate", headers=H(tokens)).json()
    assert "generated" in result
    if result["generated"]:
        assert "suggested_action" in result and "expected_effect" in result
        assert "parameter" in result["suggested_action"]
        assert "delta_pct" in result["suggested_action"]
