from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

try:
    from .client import SCENARIOS, SloGuardianMcpClient
except ImportError:  # Direct script execution through Codex stdio configuration.
    from client import SCENARIOS, SloGuardianMcpClient


mcp = FastMCP(
    "slo-guardian",
    instructions=(
        "Inspect deterministic incident evidence and submit untrusted structured recommendations. "
        "This server has no policy approval or activation capability."
    ),
)


@mcp.tool()
def list_scenarios() -> list[str]:
    """List the checked-in deterministic incident scenarios."""
    return list(SCENARIOS)


@mcp.tool()
async def prepare_incident(scenario_id: str, source: str = "fixture") -> dict[str, Any]:
    """Build and return a normalized incident packet for evidence-based reasoning."""
    return await SloGuardianMcpClient().prepare_incident(scenario_id, source)


@mcp.tool()
async def get_incident(incident_id: str) -> dict[str, Any]:
    """Read an incident, its current recommendation, and candidate validation states."""
    return await SloGuardianMcpClient().get_incident(incident_id)


@mcp.tool()
async def submit_recommendation(
    incident_id: str, recommendation: dict[str, Any]
) -> dict[str, Any]:
    """Validate and store three cited candidates without executing or approving any policy."""
    return await SloGuardianMcpClient().submit_recommendation(incident_id, recommendation)


@mcp.tool()
async def simulate_candidate(incident_id: str, policy_id: str) -> dict[str, Any]:
    """Run deterministic counterfactual simulation for a stored validated policy ID."""
    return await SloGuardianMcpClient().simulate_candidate(incident_id, policy_id)


@mcp.tool()
async def rank_candidates(incident_id: str) -> list[dict[str, Any]]:
    """Simulate and deterministically rank every valid candidate for an incident."""
    return await SloGuardianMcpClient().rank_candidates(incident_id)


@mcp.resource("slo-guardian://incidents/{incident_id}")
async def incident_resource(incident_id: str) -> str:
    """Expose a stored incident as a read-only MCP resource."""
    import json

    incident = await SloGuardianMcpClient().get_incident(incident_id)
    return json.dumps(incident, sort_keys=True, indent=2)


@mcp.prompt()
def investigate_slo_incident(scenario_id: str = "slow_dependency") -> str:
    """Guide a complete cited diagnosis and safe candidate-comparison workflow."""
    return f"""Investigate SLO Guardian scenario `{scenario_id}`.
1. Call prepare_incident and reason only from the returned packet.
2. Produce exactly three distinct Recommendation candidates using only allowed actions.
3. Cite only supplied evidence IDs in the diagnosis and every candidate.
4. Call submit_recommendation. Treat all returned rejections as authoritative.
5. Call rank_candidates and explain the deterministic ordering.
6. Stop before approval. Ask the operator to review and approve in the dashboard.
Never call service endpoints directly and never construct an executable command."""


if __name__ == "__main__":
    mcp.run(transport="stdio")
