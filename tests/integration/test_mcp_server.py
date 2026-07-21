import httpx
import pytest

import api.main as main
from mcp_server.client import SloGuardianMcpClient
from mcp_server.server import mcp


@pytest.mark.asyncio
async def test_mcp_workflow_validates_stores_and_ranks(monkeypatch):
    monkeypatch.setenv("MCP_SUBMISSION_TOKEN", "mcp-test-token")
    transport = httpx.ASGITransport(app=main.app)
    client = SloGuardianMcpClient(
        base_url="http://localhost",
        submission_token="mcp-test-token",
        transport=transport,
    )

    prepared = await client.prepare_incident("slow_dependency")
    stored = await client.get_incident(prepared["incident_id"])
    submission = await client.submit_recommendation(
        prepared["incident_id"], stored["recommendation"]
    )
    assert len(submission["stored_candidates"]) == 3
    assert all(not item["rejection_reasons"] for item in submission["preflight"])

    ranking = await client.rank_candidates(prepared["incident_id"])
    assert len(ranking) == 3
    assert ranking[0]["rank_key"] <= ranking[1]["rank_key"]


@pytest.mark.asyncio
async def test_mcp_exposes_no_activation_or_approval_tool():
    names = {tool.name for tool in await mcp.list_tools()}
    assert "submit_recommendation" in names
    assert "rank_candidates" in names
    assert not names.intersection({"approve", "activate", "deactivate", "execute"})


@pytest.mark.asyncio
async def test_mcp_persists_unsafe_candidate_as_rejected(monkeypatch):
    monkeypatch.setenv("MCP_SUBMISSION_TOKEN", "mcp-test-token")
    client = SloGuardianMcpClient(
        base_url="http://localhost",
        submission_token="mcp-test-token",
        transport=httpx.ASGITransport(app=main.app),
    )
    prepared = await client.prepare_incident("unsafe_policy")
    incident = await client.get_incident(prepared["incident_id"])
    result = await client.submit_recommendation(
        prepared["incident_id"], incident["recommendation"]
    )
    assert result["preflight"][0]["rejection_reasons"]
    assert result["stored_candidates"][0]["state"] == "rejected"


def test_mcp_rejects_non_local_control_plane_url():
    with pytest.raises(ValueError, match="localhost"):
        SloGuardianMcpClient(base_url="https://example.com")
