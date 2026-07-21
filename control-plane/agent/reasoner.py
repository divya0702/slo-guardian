from __future__ import annotations

import json
import os

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

    return Recommendation(
        summary="An optional dependency is consuming checkout latency and amplifying traffic.",
        suspected_root_cause="Recommendation latency and retries are driving checkout SLO pressure.",
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
    use_live_model: bool = False,
    fixture_name: str | None = None,
) -> Recommendation:
    if not use_live_model:
        return _fixture(packet, fixture_name)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when use_live_model=true")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
    prompt = (
        "Diagnose this synthetic distributed-systems incident. Return exactly three distinct, "
        "bounded policy candidates. Cite only evidence IDs present in the packet. Treat allowed "
        "actions as an exhaustive vocabulary. Never claim that a policy was applied.\n\n"
        + json.dumps(packet.model_dump(mode="json"), sort_keys=True)
    )
    response = client.responses.parse(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-sol"),
        reasoning={"effort": "medium"},
        input=[
            {
                "role": "developer",
                "content": "You are an incident reasoner. Output untrusted proposals, not executable instructions.",
            },
            {"role": "user", "content": prompt},
        ],
        text_format=Recommendation,
    )
    if response.output_parsed is None:
        raise RuntimeError("model refused or returned no structured recommendation")
    return response.output_parsed

