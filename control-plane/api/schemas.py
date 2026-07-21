from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PressureStatus(str, Enum):
    healthy = "healthy"
    warning = "warning"
    breached = "breached"
    insufficient_data = "insufficient_data"


class ServiceSLO(StrictModel):
    service: str
    sample_count: int
    availability: float
    error_rate: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    request_volume: int
    retry_amplification: float
    dependency_contribution_ms: float
    availability_budget_remaining_percent: float
    latency_budget_remaining_percent: float
    pressure: float
    status: PressureStatus


class GraphNode(StrictModel):
    id: str
    label: str
    traffic_class: Literal["critical", "optional", "mixed"]
    status: PressureStatus
    p99_ms: float


class GraphEdge(StrictModel):
    source: str
    target: str
    traffic_class: Literal["critical", "optional"]
    retry_amplification: float = 1.0


class ServiceGraph(StrictModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Evidence(StrictModel):
    id: str
    kind: Literal["slo", "trace", "retry", "change", "dependency"]
    service: str
    summary: str
    value: float | str | int
    unit: str | None = None
    trace_id: str | None = None


class RecentChange(StrictModel):
    id: str
    service: str
    summary: str
    timestamp: str


class IncidentPacket(StrictModel):
    incident_id: str
    scenario_id: str
    observed_at: str
    window_size: int
    service_graph: ServiceGraph
    slo_status: dict[str, ServiceSLO]
    trace_aggregates: list[dict[str, Any]]
    recent_changes: list[RecentChange]
    allowed_actions: list[str]
    evidence: list[Evidence]


class MetricName(str, Enum):
    p99_latency_ms = "p99_latency_ms"
    error_budget_remaining_percent = "error_budget_remaining_percent"
    error_rate = "error_rate"
    retry_amplification = "retry_amplification"


class ComparisonOperator(str, Enum):
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"


class MetricCondition(StrictModel):
    metric: MetricName
    operator: ComparisonOperator
    value: float


class PolicyTarget(StrictModel):
    service: Literal["gateway", "checkout", "inventory", "pricing", "recommendations"]
    route: str
    traffic_class: Literal["critical", "optional", "background"]


class ShedOptionalTraffic(StrictModel):
    type: Literal["shed_optional_traffic"]
    percentage: int = Field(ge=1, le=100)
    fallback_id: Literal["static-recommendations", "empty-recommendations"]


class RateLimit(StrictModel):
    type: Literal["rate_limit"]
    requests_per_second: int = Field(ge=1, le=1000)
    burst: int = Field(ge=1, le=2000)


class DisableRetries(StrictModel):
    type: Literal["disable_retries"]
    edge: Literal["checkout->recommendations"]


class ServeFallback(StrictModel):
    type: Literal["serve_fallback"]
    fallback_id: Literal["static-recommendations", "empty-recommendations"]


class NoAction(StrictModel):
    type: Literal["no_action"]


PolicyAction = Annotated[
    ShedOptionalTraffic | RateLimit | DisableRetries | ServeFallback | NoAction,
    Field(discriminator="type"),
]


class PolicyProposal(StrictModel):
    title: str = Field(min_length=3, max_length=120)
    target: PolicyTarget | None
    conditions: list[MetricCondition] = Field(min_length=1, max_length=4)
    action: PolicyAction
    ttl_seconds: int = Field(ge=30, le=600)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    expected_effect: str = Field(min_length=1, max_length=500)


class Recommendation(StrictModel):
    summary: str
    suspected_root_cause: str
    evidence_ids: list[str] = Field(min_length=1)
    alternative_hypotheses: list[str]
    candidates: list[PolicyProposal] = Field(min_length=3, max_length=3)
    risks: list[str]
    uncertainty: str
    confidence: float = Field(ge=0, le=1)


class CandidateResult(StrictModel):
    policy_id: str
    proposal: PolicyProposal
    state: Literal["validated", "rejected", "simulated", "approved", "active", "expired"]
    rejection_reasons: list[str] = Field(default_factory=list)


class AnalysisRequest(StrictModel):
    scenario_id: str
    source: Literal["fixture", "jaeger"] = "fixture"


class RecommendationSubmission(StrictModel):
    recommendation: Recommendation


class AnalysisResponse(StrictModel):
    analysis_id: str
    incident_id: str
    packet: IncidentPacket
    recommendation: Recommendation
    candidates: list[CandidateResult]


class SimulationRequest(StrictModel):
    policy_id: str
    scenario_id: str
    mode: Literal["counterfactual", "live"] = "counterfactual"
    request_count: int = Field(default=40, ge=20, le=200)
    concurrency: int = Field(default=5, ge=1, le=20)


class SimulationMetrics(StrictModel):
    checkout_p99_ms: float
    critical_success_rate: float
    critical_rejected: int
    optional_degradation_percent: float
    error_budget_consumption: float
    retry_amplification: float


class SimulationResponse(StrictModel):
    simulation_id: str
    policy_id: str
    mode: Literal["counterfactual", "live"]
    baseline: SimulationMetrics
    projected: SimulationMetrics
    observed: SimulationMetrics | None = None
    rank_key: list[float]
    safe: bool
    created_at: str


class ActivePolicy(StrictModel):
    policy_id: str
    action: PolicyAction
    target: PolicyTarget | None
    activated_at: str
    expires_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
