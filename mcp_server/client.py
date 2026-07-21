from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = ROOT / "control-plane"
if str(CONTROL_PLANE) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE))

from api.schemas import IncidentPacket, Recommendation  # noqa: E402
from policy_engine.validator import validate_policy  # noqa: E402


LOCAL_ENV = dotenv_values(ROOT / ".env")
SCENARIOS = (
    "healthy",
    "slow_dependency",
    "retry_storm",
    "recommendation_timeout",
    "recommendation_saturation",
    "inventory_timeout",
    "pricing_errors",
    "gateway_saturation",
    "checkout_pool_exhaustion",
    "correlated_latency",
    "unsafe_policy",
    "hallucinated_evidence",
)


class SloGuardianMcpClient:
    """A localhost-only client that keeps reliability decisions deterministic."""

    def __init__(
        self,
        base_url: str | None = None,
        submission_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("SLO_GUARDIAN_URL")
            or LOCAL_ENV.get("SLO_GUARDIAN_URL")
            or "http://127.0.0.1:8080"
        ).rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("SLO_GUARDIAN_URL must be a localhost HTTP URL")
        self.submission_token = (
            submission_token
            or os.getenv("MCP_SUBMISSION_TOKEN")
            or LOCAL_ENV.get("MCP_SUBMISSION_TOKEN")
            or "local-mcp-token"
        )
        self.transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=20.0,
            transport=self.transport,
        ) as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

    async def prepare_incident(self, scenario_id: str, source: str = "fixture") -> dict[str, Any]:
        if scenario_id not in SCENARIOS:
            raise ValueError(f"unknown scenario: {scenario_id}")
        if source not in {"fixture", "jaeger"}:
            raise ValueError("source must be fixture or jaeger")
        analysis = await self._request(
            "POST",
            "/api/v1/analyses",
            json={"scenario_id": scenario_id, "source": source},
        )
        return {
            "incident_id": analysis["incident_id"],
            "incident_packet": analysis["packet"],
            "instructions": {
                "candidate_count": 3,
                "evidence_rule": "Cite only IDs in incident_packet.evidence.",
                "execution_boundary": "Submission validates and stores proposals; it never applies them.",
                "allowed_actions": analysis["packet"]["allowed_actions"],
            },
        }

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/incidents/{incident_id}")

    async def submit_recommendation(
        self, incident_id: str, recommendation_data: dict[str, Any]
    ) -> dict[str, Any]:
        analysis = await self.get_incident(incident_id)
        packet = IncidentPacket.model_validate(analysis["packet"])
        recommendation = Recommendation.model_validate(recommendation_data)
        evidence_ids = {item.id for item in packet.evidence}
        global_reasons = []
        missing = sorted(set(recommendation.evidence_ids) - evidence_ids)
        if missing:
            global_reasons.append(f"recommendation cites unknown evidence IDs: {', '.join(missing)}")
        preflight = [
            {
                "title": candidate.title,
                "rejection_reasons": validate_policy(candidate, evidence_ids) + global_reasons,
            }
            for candidate in recommendation.candidates
        ]
        stored = await self._request(
            "POST",
            f"/api/v1/incidents/{incident_id}/recommendations",
            headers={"x-slo-mcp-token": self.submission_token},
            json={"recommendation": recommendation.model_dump(mode="json")},
        )
        return {
            "incident_id": incident_id,
            "preflight": preflight,
            "stored_candidates": stored["candidates"],
            "next_step": "Simulate or rank validated policy IDs. Human approval remains dashboard-only.",
        }

    async def simulate_candidate(self, incident_id: str, policy_id: str) -> dict[str, Any]:
        analysis = await self.get_incident(incident_id)
        candidate_ids = {item["policy_id"] for item in analysis["candidates"]}
        if policy_id not in candidate_ids:
            raise ValueError("policy ID does not belong to the supplied incident")
        return await self._request(
            "POST",
            "/api/v1/simulations",
            json={
                "policy_id": policy_id,
                "scenario_id": analysis["packet"]["scenario_id"],
                "mode": "counterfactual",
            },
        )

    async def rank_candidates(self, incident_id: str) -> list[dict[str, Any]]:
        return await self._request("POST", f"/api/v1/incidents/{incident_id}/rank")
