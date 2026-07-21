from pathlib import Path

from slo_engine.engine import calculate_slos
from trace_analyzer.fixture import build_fixture_spans, load_scenario
from trace_analyzer.incident import build_incident_packet


SCENARIOS = str(Path(__file__).parents[2] / "scenarios")


def test_slow_dependency_is_deterministic_and_cited():
    scenario = load_scenario("slow_dependency", SCENARIOS)
    first = calculate_slos(build_fixture_spans(scenario))
    second = calculate_slos(build_fixture_spans(scenario))
    assert first == second
    assert first["recommendations"].status.value == "breached"
    assert first["recommendations"].retry_amplification == 3
    packet = build_incident_packet(scenario, first)
    assert len(packet.service_graph.nodes) == 5
    assert all(item.id.startswith("ev_") for item in packet.evidence)


def test_healthy_scenario_stays_green():
    scenario = load_scenario("healthy", SCENARIOS)
    slos = calculate_slos(build_fixture_spans(scenario))
    assert all(value.status.value == "healthy" for value in slos.values())

