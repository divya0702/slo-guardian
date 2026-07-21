from __future__ import annotations

import asyncio
import os
import statistics
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from api.schemas import PolicyProposal, SimulationMetrics, SimulationResponse


SEVERITY = {
    "no_action": 0,
    "disable_retries": 1,
    "serve_fallback": 2,
    "rate_limit": 3,
    "shed_optional_traffic": 4,
}


def _nearest_p99(values: list[float]) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return round(ordered[max(0, int(len(ordered) * 0.99) - 1)], 2)


def counterfactual_metrics(
    scenario: dict[str, Any], proposal: PolicyProposal
) -> tuple[SimulationMetrics, SimulationMetrics]:
    latency = scenario.get("latency_ms", {})
    errors = scenario.get("error_rate", {})
    baseline_p99 = float(latency.get("checkout", 100))
    retries = int(scenario.get("recommendation_retries", 0))
    critical_error = max(float(errors.get("checkout", 0)), float(errors.get("inventory", 0)), float(errors.get("pricing", 0)))
    baseline = SimulationMetrics(
        checkout_p99_ms=round(baseline_p99, 2),
        critical_success_rate=round(1 - critical_error, 4),
        critical_rejected=0,
        optional_degradation_percent=0,
        error_budget_consumption=round(max(0, critical_error / 0.01, baseline_p99 / 1000), 3),
        retry_amplification=float(1 + retries),
    )
    action = proposal.action
    recommendation_latency = float(latency.get("recommendations", 0))
    projected_p99 = baseline_p99
    degradation = 0.0
    projected_retries = float(1 + retries)
    if action.type == "serve_fallback":
        projected_p99 = max(80, baseline_p99 - recommendation_latency * 0.9)
        degradation = 100.0
        projected_retries = 1.0
    elif action.type == "disable_retries":
        retry_fraction = retries / (retries + 1) if retries else 0
        projected_p99 = max(80, baseline_p99 - recommendation_latency * retry_fraction * 0.65)
        projected_retries = 1.0
    elif action.type == "shed_optional_traffic":
        ratio = action.percentage / 100
        projected_p99 = max(80, baseline_p99 - recommendation_latency * ratio * 0.75)
        degradation = float(action.percentage)
        projected_retries = round(1 + retries * (1 - ratio), 2)
    elif action.type == "rate_limit":
        request_count = int(scenario.get("request_count", 100))
        accepted = min(request_count, action.requests_per_second + action.burst)
        ratio = max(0.0, 1 - accepted / request_count)
        projected_p99 = max(80, baseline_p99 - recommendation_latency * ratio * 0.7)
        degradation = round(ratio * 100, 2)
        projected_retries = round(1 + retries * (1 - ratio), 2)
    projected = SimulationMetrics(
        checkout_p99_ms=round(projected_p99, 2),
        critical_success_rate=baseline.critical_success_rate,
        critical_rejected=0,
        optional_degradation_percent=round(degradation, 2),
        error_budget_consumption=round(max(0, critical_error / 0.01, projected_p99 / 1000), 3),
        retry_amplification=projected_retries,
    )
    return baseline, projected


def ranking_key(metrics: SimulationMetrics, proposal: PolicyProposal) -> list[float]:
    return [
        float(metrics.critical_rejected),
        round(1 - metrics.critical_success_rate, 6),
        0.0 if metrics.checkout_p99_ms <= 1000 else 1.0,
        metrics.error_budget_consumption,
        metrics.checkout_p99_ms,
        metrics.optional_degradation_percent,
        float(SEVERITY[proposal.action.type]),
    ]


def canonical_command(policy_id: str, proposal: PolicyProposal) -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "action_type": proposal.action.type,
        "parameters": proposal.action.model_dump(exclude={"type"}, mode="json"),
        "ttl_seconds": proposal.ttl_seconds,
    }


async def _set_policy(command: dict[str, Any] | None) -> None:
    base = os.getenv("CHECKOUT_URL", "http://checkout:8000")
    token = os.getenv("INTERNAL_REPLAY_TOKEN", "local-demo-token")
    async with httpx.AsyncClient(timeout=5.0) as client:
        if command is None:
            response = await client.delete(
                f"{base}/internal/policy", headers={"x-slo-internal-token": token}
            )
        else:
            response = await client.post(
                f"{base}/internal/policy",
                json=command,
                headers={"x-slo-internal-token": token},
            )
        response.raise_for_status()


async def live_replay(
    scenario_id: str,
    policy_id: str,
    proposal: PolicyProposal,
    request_count: int,
    concurrency: int,
) -> SimulationMetrics:
    command = canonical_command(policy_id, proposal)
    await _set_policy(command)
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    successes = 0
    fallbacks = 0
    attempts = 0
    gateway = os.getenv("GATEWAY_URL", "http://gateway:8000")

    async def one(index: int) -> None:
        nonlocal successes, fallbacks, attempts
        async with semaphore:
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    response = await client.get(
                        f"{gateway}/checkout",
                        params={"scenario": scenario_id, "customer_id": f"demo-{index}"},
                        headers={"x-request-id": f"replay-{scenario_id}-{index}"},
                    )
                latencies.append((time.perf_counter() - started) * 1000)
                if response.is_success:
                    successes += 1
                    payload = response.json()
                    fallbacks += int(bool(payload.get("recommendation_fallback")))
                    attempts += int(payload.get("recommendation_attempts", 1))
            except httpx.HTTPError:
                latencies.append((time.perf_counter() - started) * 1000)

    try:
        await asyncio.gather(*(one(index) for index in range(request_count)))
    finally:
        await _set_policy(None)
    return SimulationMetrics(
        checkout_p99_ms=_nearest_p99(latencies),
        critical_success_rate=round(successes / request_count, 4),
        critical_rejected=0,
        optional_degradation_percent=round(fallbacks / request_count * 100, 2),
        error_budget_consumption=round(max(0, (1 - successes / request_count) / 0.01, _nearest_p99(latencies) / 1000), 3),
        retry_amplification=round(attempts / request_count, 2),
    )


def make_result(
    simulation_id: str,
    policy_id: str,
    mode: str,
    proposal: PolicyProposal,
    baseline: SimulationMetrics,
    projected: SimulationMetrics,
    observed: SimulationMetrics | None,
) -> SimulationResponse:
    scored = observed or projected
    return SimulationResponse(
        simulation_id=simulation_id,
        policy_id=policy_id,
        mode=mode,
        baseline=baseline,
        projected=projected,
        observed=observed,
        rank_key=ranking_key(scored, proposal),
        safe=scored.critical_rejected == 0,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

