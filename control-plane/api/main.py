from __future__ import annotations

import os
import secrets
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, select

from agent.reasoner import reason_about_incident
from api.database import (
    AuditRecord,
    IncidentRecord,
    PolicyRecord,
    SessionLocal,
    SimulationRecord,
    initialize_database,
)
from api.schemas import (
    ActivePolicy,
    AnalysisRequest,
    AnalysisResponse,
    CandidateResult,
    IncidentPacket,
    PolicyProposal,
    Recommendation,
    RecommendationSubmission,
    SimulationRequest,
    SimulationResponse,
)
from policy_engine.validator import validate_policy
from simulator.engine import (
    _set_policy,
    canonical_command,
    counterfactual_metrics,
    live_replay,
    make_result,
)
from slo_engine.engine import calculate_slos
from trace_analyzer.fixture import build_fixture_spans, load_scenario
from trace_analyzer.incident import build_incident_packet
from trace_analyzer.jaeger import JaegerTraceSource



@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="SLO Guardian Control Plane", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


def _scenario(scenario_id: str) -> dict:
    return load_scenario(scenario_id, os.getenv("SCENARIOS_DIR", "scenarios"))


def _analysis_from_record(record: IncidentRecord, policies: list[PolicyRecord]) -> AnalysisResponse:
    packet = IncidentPacket.model_validate(record.packet)
    recommendation = Recommendation.model_validate(record.recommendation)
    candidates = [
        CandidateResult(
            policy_id=policy.id,
            proposal=PolicyProposal.model_validate(policy.proposal),
            state=policy.state,
            rejection_reasons=policy.rejection_reasons,
        )
        for policy in policies
    ]
    return AnalysisResponse(
        analysis_id=record.id,
        incident_id=record.id,
        packet=packet,
        recommendation=recommendation,
        candidates=candidates,
    )


def _replace_recommendation(
    session,
    incident_record: IncidentRecord,
    packet: IncidentPacket,
    recommendation: Recommendation,
    reasoning_source: str,
) -> list[PolicyRecord]:
    """Validate and persist untrusted reasoning output as non-executable candidates."""
    for old_policy in session.scalars(
        select(PolicyRecord).where(PolicyRecord.incident_id == packet.incident_id)
    ):
        session.delete(old_policy)

    incident_record.recommendation = recommendation.model_dump(mode="json")
    evidence_ids = {item.id for item in packet.evidence}
    global_missing = sorted(set(recommendation.evidence_ids) - evidence_ids)
    policy_records: list[PolicyRecord] = []
    for proposal in recommendation.candidates:
        reasons = validate_policy(proposal, evidence_ids)
        if global_missing:
            reasons.append(f"recommendation cites unknown evidence IDs: {', '.join(global_missing)}")
        record = PolicyRecord(
            id="pol_" + uuid.uuid4().hex[:12],
            incident_id=packet.incident_id,
            proposal=proposal.model_dump(mode="json"),
            state="rejected" if reasons else "validated",
            rejection_reasons=reasons,
        )
        session.add(record)
        policy_records.append(record)
    session.add(
        AuditRecord(
            id="aud_" + uuid.uuid4().hex[:12],
            event_type="recommendation_validated",
            payload={
                "incident_id": packet.incident_id,
                "reasoning_source": reasoning_source,
                "candidate_count": len(policy_records),
            },
        )
    )
    return policy_records


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        with SessionLocal() as session:
            session.execute(select(IncidentRecord).limit(1))
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc


@app.post("/api/v1/analyses", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    try:
        scenario = _scenario(request.scenario_id)
        spans = (
            build_fixture_spans(scenario)
            if request.source == "fixture"
            else await JaegerTraceSource().fetch_spans()
        )
        slos = calculate_slos(spans)
        packet = build_incident_packet(scenario, slos)
        recommendation = reason_about_incident(
            packet,
            fixture_name=scenario.get("agent_fixture"),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with SessionLocal() as session:
        existing = session.get(IncidentRecord, packet.incident_id)
        if existing:
            existing.packet = packet.model_dump(mode="json")
            incident_record = existing
        else:
            incident_record = IncidentRecord(
                id=packet.incident_id,
                scenario_id=packet.scenario_id,
                packet=packet.model_dump(mode="json"),
                recommendation=recommendation.model_dump(mode="json"),
            )
            session.add(incident_record)
        policy_records = _replace_recommendation(
            session, incident_record, packet, recommendation, "deterministic_fixture"
        )
        session.add(
            AuditRecord(
                id="aud_" + uuid.uuid4().hex[:12],
                event_type="analysis_completed",
                payload={"incident_id": packet.incident_id, "scenario_id": packet.scenario_id},
            )
        )
        session.commit()
        return _analysis_from_record(incident_record, policy_records)


@app.post(
    "/api/v1/incidents/{incident_id}/recommendations",
    response_model=AnalysisResponse,
)
def submit_codex_recommendation(
    incident_id: str,
    submission: RecommendationSubmission,
    x_slo_mcp_token: str | None = Header(default=None),
):
    expected = os.getenv("MCP_SUBMISSION_TOKEN", "local-mcp-token")
    if not x_slo_mcp_token or not secrets.compare_digest(x_slo_mcp_token, expected):
        raise HTTPException(status_code=401, detail="invalid MCP submission token")

    with SessionLocal() as session:
        incident_record = session.get(IncidentRecord, incident_id)
        if not incident_record:
            raise HTTPException(status_code=404, detail="incident not found")
        packet = IncidentPacket.model_validate(incident_record.packet)
        policy_records = _replace_recommendation(
            session,
            incident_record,
            packet,
            submission.recommendation,
            "codex_mcp",
        )
        session.commit()
        return _analysis_from_record(incident_record, policy_records)


@app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str):
    with SessionLocal() as session:
        record = session.get(IncidentRecord, analysis_id)
        if not record:
            raise HTTPException(status_code=404, detail="analysis not found")
        policies = list(
            session.scalars(select(PolicyRecord).where(PolicyRecord.incident_id == analysis_id))
        )
        return _analysis_from_record(record, policies)


@app.get("/api/v1/incidents")
def incidents():
    with SessionLocal() as session:
        records = list(session.scalars(select(IncidentRecord).order_by(IncidentRecord.created_at.desc())))
        return [
            {"incident_id": item.id, "scenario_id": item.scenario_id, "created_at": item.created_at}
            for item in records
        ]


@app.get("/api/v1/incidents/{incident_id}", response_model=AnalysisResponse)
def incident(incident_id: str):
    return get_analysis(incident_id)


@app.get("/api/v1/incidents/{incident_id}/graph")
def incident_graph(incident_id: str):
    result = get_analysis(incident_id)
    return result.packet.service_graph


@app.post("/api/v1/simulations", response_model=SimulationResponse)
async def simulate(request: SimulationRequest):
    with SessionLocal() as session:
        policy = session.get(PolicyRecord, request.policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail="policy not found")
        if policy.state == "rejected":
            raise HTTPException(status_code=409, detail="rejected policies cannot be simulated")
        proposal = PolicyProposal.model_validate(policy.proposal)
        scenario = _scenario(request.scenario_id)
        baseline, projected = counterfactual_metrics(scenario, proposal)
        observed = None
        if request.mode == "live":
            try:
                observed = await live_replay(
                    request.scenario_id,
                    policy.id,
                    proposal,
                    request.request_count,
                    request.concurrency,
                )
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="live replay failed") from exc
        simulation_id = "sim_" + uuid.uuid4().hex[:12]
        result = make_result(
            simulation_id,
            policy.id,
            request.mode,
            proposal,
            baseline,
            projected,
            observed,
        )
        policy.state = "simulated"
        session.add(
            SimulationRecord(
                id=simulation_id,
                policy_id=policy.id,
                result=result.model_dump(mode="json"),
            )
        )
        session.add(
            AuditRecord(
                id="aud_" + uuid.uuid4().hex[:12],
                event_type="simulation_completed",
                payload={"simulation_id": simulation_id, "policy_id": policy.id, "mode": request.mode},
            )
        )
        session.commit()
        return result


@app.post("/api/v1/incidents/{incident_id}/rank", response_model=list[SimulationResponse])
def rank_incident_candidates(incident_id: str):
    with SessionLocal() as session:
        incident = session.get(IncidentRecord, incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="incident not found")
        scenario = _scenario(incident.scenario_id)
        policies = list(
            session.scalars(
                select(PolicyRecord).where(
                    PolicyRecord.incident_id == incident_id,
                    PolicyRecord.state != "rejected",
                )
            )
        )
        results: list[SimulationResponse] = []
        for policy in policies:
            proposal = PolicyProposal.model_validate(policy.proposal)
            baseline, projected = counterfactual_metrics(scenario, proposal)
            simulation_id = "sim_" + uuid.uuid4().hex[:12]
            result = make_result(
                simulation_id,
                policy.id,
                "counterfactual",
                proposal,
                baseline,
                projected,
                None,
            )
            policy.state = "simulated"
            session.add(
                SimulationRecord(
                    id=simulation_id,
                    policy_id=policy.id,
                    result=result.model_dump(mode="json"),
                )
            )
            results.append(result)
        results.sort(key=lambda item: tuple(item.rank_key))
        session.add(
            AuditRecord(
                id="aud_" + uuid.uuid4().hex[:12],
                event_type="candidates_ranked",
                payload={
                    "incident_id": incident_id,
                    "ordered_policy_ids": [item.policy_id for item in results],
                },
            )
        )
        session.commit()
        return results


@app.get("/api/v1/simulations/{simulation_id}", response_model=SimulationResponse)
def get_simulation(simulation_id: str):
    with SessionLocal() as session:
        record = session.get(SimulationRecord, simulation_id)
        if not record:
            raise HTTPException(status_code=404, detail="simulation not found")
        return SimulationResponse.model_validate(record.result)


@app.post("/api/v1/policies/{policy_id}/approve")
async def approve(policy_id: str):
    with SessionLocal() as session:
        policy = session.get(PolicyRecord, policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail="policy not found")
        if policy.state != "simulated":
            raise HTTPException(status_code=409, detail="only simulated policies may be approved")
        proposal = PolicyProposal.model_validate(policy.proposal)
        command = canonical_command(policy.id, proposal)
        try:
            await _set_policy(command)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="policy adapter rejected activation") from exc
        for active in session.scalars(select(PolicyRecord).where(PolicyRecord.state == "active")):
            active.state = "expired"
        policy.state = "active"
        session.add(
            AuditRecord(
                id="aud_" + uuid.uuid4().hex[:12],
                event_type="policy_activated",
                payload={"policy_id": policy.id, "canonical_action": proposal.action.type},
            )
        )
        session.commit()
        return {"policy_id": policy.id, "state": "active", "command": command}


@app.post("/api/v1/policies/{policy_id}/deactivate")
async def deactivate(policy_id: str):
    with SessionLocal() as session:
        policy = session.get(PolicyRecord, policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail="policy not found")
        try:
            await _set_policy(None)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="policy adapter unavailable") from exc
        policy.state = "expired"
        session.commit()
        return {"policy_id": policy.id, "state": "expired"}


@app.get("/api/v1/policies/active")
async def active_policy():
    token = os.getenv("INTERNAL_REPLAY_TOKEN", "local-demo-token")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                f"{os.getenv('CHECKOUT_URL', 'http://checkout:8000')}/internal/policy",
                headers={"x-slo-internal-token": token},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="policy adapter unavailable") from exc
    if payload.get("status") == "inactive":
        return payload
    return payload


@app.post("/api/v1/demo/reset")
async def reset_demo():
    try:
        await _set_policy(None)
    except httpx.HTTPError:
        # Database reset remains useful when the synthetic service graph is not running.
        pass
    with SessionLocal() as session:
        session.execute(delete(AuditRecord))
        session.execute(delete(SimulationRecord))
        session.execute(delete(PolicyRecord))
        session.execute(delete(IncidentRecord))
        session.commit()
    return {"status": "reset"}
