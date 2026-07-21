from pathlib import Path

import pytest

from agent.reasoner import reason_about_incident
from policy_engine.validator import validate_policy
from slo_engine.engine import calculate_slos
from trace_analyzer.fixture import build_fixture_spans, load_scenario
from trace_analyzer.incident import build_incident_packet


SCENARIOS = str(Path(__file__).parents[2] / "scenarios")


def packet(scenario_id):
    scenario = load_scenario(scenario_id, SCENARIOS)
    return scenario, build_incident_packet(scenario, calculate_slos(build_fixture_spans(scenario)))


def test_fixture_returns_three_cited_candidates():
    scenario, incident = packet("slow_dependency")
    result = reason_about_incident(incident, fixture_name=scenario.get("agent_fixture"))
    valid_ids = {item.id for item in incident.evidence}
    assert len(result.candidates) == 3
    assert set(result.evidence_ids) <= valid_ids
    assert all(set(candidate.evidence_ids) <= valid_ids for candidate in result.candidates)


def test_unsafe_fixture_is_rejected():
    scenario, incident = packet("unsafe_policy")
    result = reason_about_incident(incident, fixture_name=scenario["agent_fixture"])
    reasons = validate_policy(result.candidates[0], {item.id for item in incident.evidence})
    assert reasons


def test_hallucinated_fixture_is_rejected():
    scenario, incident = packet("hallucinated_evidence")
    result = reason_about_incident(incident, fixture_name=scenario["agent_fixture"])
    reasons = validate_policy(result.candidates[0], {item.id for item in incident.evidence})
    assert any("unknown evidence" in reason for reason in reasons)


@pytest.mark.parametrize(
    ("scenario_id", "diagnosis_term"),
    [
        ("healthy", "No meaningful incident"),
        ("slow_dependency", "Recommendation latency"),
        ("retry_storm", "retry amplification"),
        ("recommendation_timeout", "timeouts"),
        ("recommendation_saturation", "saturation"),
        ("inventory_timeout", "Inventory timeouts"),
        ("pricing_errors", "Pricing errors"),
        ("gateway_saturation", "Gateway saturation"),
        ("checkout_pool_exhaustion", "client pool"),
        ("correlated_latency", "critical-dependency latency"),
        ("unsafe_policy", "Recommendation latency"),
        ("hallucinated_evidence", "Recommendation latency"),
    ],
)
def test_all_scenarios_have_expected_diagnosis(scenario_id, diagnosis_term):
    scenario, incident = packet(scenario_id)
    result = reason_about_incident(incident, fixture_name=scenario.get("agent_fixture"))
    assert diagnosis_term.lower() in result.suspected_root_cause.lower()
    assert len(result.candidates) == 3
