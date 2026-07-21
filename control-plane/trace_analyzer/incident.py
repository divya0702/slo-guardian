from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from api.schemas import (
    Evidence,
    GraphEdge,
    GraphNode,
    IncidentPacket,
    RecentChange,
    ServiceGraph,
    ServiceSLO,
)


ALLOWED_ACTIONS = [
    "shed_optional_traffic",
    "rate_limit",
    "disable_retries",
    "serve_fallback",
    "no_action",
]


def _evidence_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "ev_" + hashlib.sha256(canonical.encode()).hexdigest()[:12]


def build_incident_packet(scenario: dict[str, Any], slos: dict[str, ServiceSLO]) -> IncidentPacket:
    scenario_id = scenario["id"]
    incident_id = "inc_" + hashlib.sha256(scenario_id.encode()).hexdigest()[:10]
    evidence: list[Evidence] = []
    for service, slo in sorted(slos.items()):
        payload = {"kind": "slo", "service": service, "p99_ms": slo.p99_ms, "pressure": slo.pressure}
        evidence.append(
            Evidence(
                id=_evidence_id(payload),
                kind="slo",
                service=service,
                summary=f"{service} p99 is {slo.p99_ms} ms with {slo.status.value} SLO pressure",
                value=slo.p99_ms,
                unit="ms",
            )
        )
        if slo.retry_amplification > 1:
            retry_payload = {"kind": "retry", "service": service, "value": slo.retry_amplification}
            evidence.append(
                Evidence(
                    id=_evidence_id(retry_payload),
                    kind="retry",
                    service=service,
                    summary=f"{service} generated {slo.retry_amplification} attempts per request",
                    value=slo.retry_amplification,
                    unit="attempts/request",
                )
            )

    changes: list[RecentChange] = []
    for index, change in enumerate(scenario.get("recent_changes", [])):
        change_id = f"chg_{scenario_id}_{index}"
        changes.append(
            RecentChange(
                id=change_id,
                service=change["service"],
                summary=change["summary"],
                timestamp="2026-07-21T12:00:00+00:00",
            )
        )
        payload = {"kind": "change", "service": change["service"], "summary": change["summary"]}
        evidence.append(
            Evidence(
                id=_evidence_id(payload),
                kind="change",
                service=change["service"],
                summary=change["summary"],
                value=change_id,
            )
        )

    nodes = [
        GraphNode(
            id=service,
            label=service.replace("_", " ").title(),
            traffic_class="optional" if service == "recommendations" else ("mixed" if service == "checkout" else "critical"),
            status=slo.status,
            p99_ms=slo.p99_ms,
        )
        for service, slo in sorted(slos.items())
    ]
    rec_retry = slos.get("recommendations").retry_amplification if "recommendations" in slos else 1
    edges = [
        GraphEdge(source="gateway", target="checkout", traffic_class="critical"),
        GraphEdge(source="checkout", target="inventory", traffic_class="critical"),
        GraphEdge(source="checkout", target="pricing", traffic_class="critical"),
        GraphEdge(
            source="checkout",
            target="recommendations",
            traffic_class="optional",
            retry_amplification=rec_retry,
        ),
    ]
    aggregates = [
        {
            "service": name,
            "p50_ms": value.p50_ms,
            "p95_ms": value.p95_ms,
            "p99_ms": value.p99_ms,
            "error_rate": value.error_rate,
            "retry_amplification": value.retry_amplification,
        }
        for name, value in sorted(slos.items())
    ]
    return IncidentPacket(
        incident_id=incident_id,
        scenario_id=scenario_id,
        observed_at=datetime.now(timezone.utc).isoformat(),
        window_size=int(scenario.get("request_count", 100)),
        service_graph=ServiceGraph(nodes=nodes, edges=edges),
        slo_status=slos,
        trace_aggregates=aggregates,
        recent_changes=changes,
        allowed_actions=ALLOWED_ACTIONS,
        evidence=evidence,
    )

