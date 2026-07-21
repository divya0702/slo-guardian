from __future__ import annotations

from api.schemas import (
    DisableRetries,
    IncidentPacket,
    MetricCondition,
    NoAction,
    PolicyProposal,
    PolicyTarget,
    Recommendation,
    ServeFallback,
    ShedOptionalTraffic,
)


def _conditions() -> list[MetricCondition]:
    return [MetricCondition(metric="p99_latency_ms", operator="gt", value=300)]


def _fixture(packet: IncidentPacket, fixture_name: str | None = None) -> Recommendation:
    evidence = [item.id for item in packet.evidence]
    rec_evidence = [item.id for item in packet.evidence if item.service == "recommendations"] or evidence[:1]
    checkout_evidence = [item.id for item in packet.evidence if item.service == "checkout"] or evidence[:1]
    primary = rec_evidence[:2]

    if packet.scenario_id == "healthy":
        candidates = [
            PolicyProposal(
                title=f"No intervention {index + 1}",
                target=None,
                conditions=[MetricCondition(metric="error_rate", operator="lte", value=0.01)],
                action=NoAction(type="no_action"),
                ttl_seconds=60,
                evidence_ids=evidence[:1],
                expected_effect="Preserve the healthy baseline.",
            )
            for index in range(3)
        ]
        return Recommendation(
            summary="The service graph is within its configured SLOs.",
            suspected_root_cause="No meaningful incident is present.",
            evidence_ids=evidence[:2],
            alternative_hypotheses=[],
            candidates=candidates,
            risks=["Unnecessary intervention could degrade healthy traffic."],
            uncertainty="Fixture data is synthetic and bounded to the observation window.",
            confidence=0.98,
        )

    critical_diagnoses = {
        "inventory_timeout": ("inventory", "Inventory timeouts are the primary critical-path failure."),
        "pricing_errors": ("pricing", "Pricing errors are the primary critical-path failure."),
        "gateway_saturation": ("gateway", "Gateway saturation is the primary source of request failure."),
        "correlated_latency": ("inventory", "Shared critical-dependency latency, not recommendations, explains the correlation."),
    }
    if packet.scenario_id in critical_diagnoses:
        service, diagnosis = critical_diagnoses[packet.scenario_id]
        cited = [item.id for item in packet.evidence if item.service == service][:2] or evidence[:1]
        candidates = [
            PolicyProposal(
                title=f"Escalate without unsafe shedding {index + 1}",
                target=None,
                conditions=[MetricCondition(metric="p99_latency_ms", operator="gt", value=300)],
                action=NoAction(type="no_action"),
                ttl_seconds=60,
                evidence_ids=cited,
                expected_effect="Protect critical checkout traffic while the critical dependency is repaired.",
            )
            for index in range(3)
        ]
        return Recommendation(
            summary="No allowlisted load-shedding action can safely repair this critical-path incident.",
            suspected_root_cause=diagnosis,
            evidence_ids=cited,
            alternative_hypotheses=["A shared network or client-pool constraint may contribute."],
            candidates=candidates,
            risks=["The incident continues until the critical dependency recovers."],
            uncertainty="Synthetic traces do not include host-level resource telemetry.",
            confidence=0.9,
        )

    target = PolicyTarget(
        service="checkout", route="/dependencies/recommendations", traffic_class="optional"
    )
    candidates = [
        PolicyProposal(
            title="Serve static recommendations",
            target=target,
            conditions=_conditions(),
            action=ServeFallback(type="serve_fallback", fallback_id="static-recommendations"),
            ttl_seconds=300,
            evidence_ids=primary,
            expected_effect="Remove the optional recommendation wait from checkout latency.",
        ),
        PolicyProposal(
            title="Disable recommendation retries",
            target=target,
            conditions=[MetricCondition(metric="retry_amplification", operator="gt", value=1)],
            action=DisableRetries(type="disable_retries", edge="checkout->recommendations"),
            ttl_seconds=300,
            evidence_ids=primary,
            expected_effect="Reduce amplified calls while preserving the original optional attempt.",
        ),
        PolicyProposal(
            title="Shed half of optional recommendation calls",
            target=target,
            conditions=_conditions(),
            action=ShedOptionalTraffic(
                type="shed_optional_traffic",
                percentage=50,
                fallback_id="static-recommendations",
            ),
            ttl_seconds=300,
            evidence_ids=primary,
            expected_effect="Reduce optional dependency load and use a safe fallback.",
        ),
    ]

    if fixture_name == "unsafe":
        candidates[0] = PolicyProposal.model_validate(
            {
                "title": "Unsafe checkout shedding",
                "target": {"service": "checkout", "route": "/checkout", "traffic_class": "critical"},
                "conditions": [{"metric": "p99_latency_ms", "operator": "gt", "value": 300}],
                "action": {"type": "shed_optional_traffic", "percentage": 50, "fallback_id": "static-recommendations"},
                "ttl_seconds": 300,
                "evidence_ids": checkout_evidence[:1],
                "expected_effect": "Unsafe fixture used to prove deterministic rejection.",
            }
        )
    if fixture_name == "hallucinated":
        candidates[0] = candidates[0].model_copy(update={"evidence_ids": ["ev_does_not_exist"]})

    root_cause = {
        "retry_storm": "Recommendation retry amplification is exhausting checkout dependency capacity.",
        "recommendation_timeout": "Recommendation timeouts are holding the optional checkout branch open.",
        "recommendation_saturation": "Recommendation worker saturation is driving optional dependency latency.",
        "checkout_pool_exhaustion": "Recommendation retries are exhausting the checkout client pool.",
    }.get(packet.scenario_id, "Recommendation latency and retries are driving checkout SLO pressure.")
    return Recommendation(
        summary="An optional dependency is consuming checkout latency and amplifying traffic.",
        suspected_root_cause=root_cause,
        evidence_ids=list(dict.fromkeys(primary + checkout_evidence[:1])),
        alternative_hypotheses=[
            "A shared client pool may be increasing queue time.",
            "Gateway saturation may contribute to end-to-end latency.",
        ],
        candidates=candidates,
        risks=[
            "Personalization quality is temporarily reduced.",
            "A fallback could mask a persistent recommendation defect.",
        ],
        uncertainty="The incident packet contains aggregate synthetic traces, not host-level metrics.",
        confidence=0.86,
    )


def reason_about_incident(
    packet: IncidentPacket,
    fixture_name: str | None = None,
) -> Recommendation:
    """Return the recorded deterministic recommendation used by standalone demo mode.

    Interactive GPT reasoning is deliberately outside the web application. Codex reads incident
    packets and submits untrusted structured recommendations through the local MCP server.
    """
    return _fixture(packet, fixture_name)
