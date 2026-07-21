from pathlib import Path

from agent.reasoner import reason_about_incident
from simulator.engine import counterfactual_metrics, ranking_key
from slo_engine.engine import calculate_slos
from trace_analyzer.fixture import build_fixture_spans, load_scenario
from trace_analyzer.incident import build_incident_packet


SCENARIOS = str(Path(__file__).parents[2] / "scenarios")


def test_fallback_improves_checkout_without_critical_rejection():
    scenario = load_scenario("slow_dependency", SCENARIOS)
    packet = build_incident_packet(scenario, calculate_slos(build_fixture_spans(scenario)))
    proposal = reason_about_incident(packet).candidates[0]
    baseline, projected = counterfactual_metrics(scenario, proposal)
    assert projected.checkout_p99_ms < baseline.checkout_p99_ms
    assert projected.critical_rejected == 0
    assert ranking_key(projected, proposal)[0] == 0

