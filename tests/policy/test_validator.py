import pytest
from pydantic import ValidationError

from api.schemas import PolicyProposal
from policy_engine.validator import validate_policy


def proposal(**changes):
    data = {
        "title": "Serve safe fallback",
        "target": {"service": "checkout", "route": "/dependencies/recommendations", "traffic_class": "optional"},
        "conditions": [{"metric": "p99_latency_ms", "operator": "gt", "value": 800}],
        "action": {"type": "serve_fallback", "fallback_id": "static-recommendations"},
        "ttl_seconds": 300,
        "evidence_ids": ["ev_real"],
        "expected_effect": "Remove optional latency.",
    }
    data.update(changes)
    return PolicyProposal.model_validate(data)


def test_accepts_allowlisted_optional_fallback():
    assert validate_policy(proposal(), {"ev_real"}) == []


def test_rejects_critical_checkout_shedding():
    unsafe = proposal(
        target={"service": "checkout", "route": "/checkout", "traffic_class": "critical"},
        action={"type": "shed_optional_traffic", "percentage": 50, "fallback_id": "static-recommendations"},
    )
    reasons = validate_policy(unsafe, {"ev_real"})
    assert any("critical" in reason for reason in reasons)
    assert any("optional recommendation" in reason for reason in reasons)


def test_rejects_hallucinated_evidence():
    assert validate_policy(proposal(), {"ev_other"}) == ["unknown evidence IDs: ev_real"]


def test_forbids_unknown_model_fields():
    with pytest.raises(ValidationError):
        proposal(backdoor_command="rm -rf /tmp")


def test_enforces_ttl_bounds():
    with pytest.raises(ValidationError):
        proposal(ttl_seconds=10000)

