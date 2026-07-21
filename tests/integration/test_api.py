from fastapi.testclient import TestClient

import api.main as main


def test_analysis_simulation_and_approval_lifecycle(monkeypatch):
    async def fake_set_policy(command):
        return None

    monkeypatch.setattr(main, "_set_policy", fake_set_policy)
    with TestClient(main.app) as client:
        analysis = client.post(
            "/api/v1/analyses",
            json={"scenario_id": "slow_dependency", "source": "fixture"},
        )
        assert analysis.status_code == 200, analysis.text
        payload = analysis.json()
        assert len(payload["candidates"]) == 3
        policy_id = next(
            candidate["policy_id"]
            for candidate in payload["candidates"]
            if candidate["state"] == "validated"
        )
        ranking = client.post(f"/api/v1/incidents/{payload['incident_id']}/rank")
        assert ranking.status_code == 200, ranking.text
        assert len(ranking.json()) == 3
        assert ranking.json()[0]["rank_key"] <= ranking.json()[1]["rank_key"]
        simulation = client.post(
            "/api/v1/simulations",
            json={
                "policy_id": policy_id,
                "scenario_id": "slow_dependency",
                "mode": "counterfactual",
            },
        )
        assert simulation.status_code == 200, simulation.text
        assert simulation.json()["safe"] is True
        approved = client.post(f"/api/v1/policies/{policy_id}/approve")
        assert approved.status_code == 200, approved.text
        assert approved.json()["command"]["action_type"] in {
            "serve_fallback",
            "disable_retries",
            "shed_optional_traffic",
        }
        reset = client.post("/api/v1/demo/reset")
        assert reset.status_code == 200
        assert client.get("/api/v1/incidents").json() == []


def test_rejected_policy_cannot_be_simulated():
    with TestClient(main.app) as client:
        analysis = client.post(
            "/api/v1/analyses",
            json={"scenario_id": "unsafe_policy", "source": "fixture"},
        ).json()
        rejected = next(item for item in analysis["candidates"] if item["state"] == "rejected")
        response = client.post(
            "/api/v1/simulations",
            json={"policy_id": rejected["policy_id"], "scenario_id": "unsafe_policy"},
        )
        assert response.status_code == 409


def test_codex_submission_requires_token_and_stores_validated_ids(monkeypatch):
    monkeypatch.setenv("MCP_SUBMISSION_TOKEN", "test-mcp-token")
    with TestClient(main.app) as client:
        original = client.post(
            "/api/v1/analyses",
            json={"scenario_id": "slow_dependency", "source": "fixture"},
        ).json()
        path = f"/api/v1/incidents/{original['incident_id']}/recommendations"
        body = {"recommendation": original["recommendation"]}
        assert client.post(path, json=body).status_code == 401

        submitted = client.post(
            path,
            json=body,
            headers={"x-slo-mcp-token": "test-mcp-token"},
        )
        assert submitted.status_code == 200, submitted.text
        assert len(submitted.json()["candidates"]) == 3
        assert all(item["policy_id"].startswith("pol_") for item in submitted.json()["candidates"])
