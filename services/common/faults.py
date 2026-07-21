from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Any

from fastapi import HTTPException, Request


SCENARIO_FAULTS: dict[str, dict[str, dict[str, float]]] = {
    "slow_dependency": {"recommendations": {"latency_ms": 820}},
    "retry_storm": {"recommendations": {"latency_ms": 500, "error_rate": 0.35}},
    "recommendation_timeout": {"recommendations": {"latency_ms": 1000, "error_rate": 1.0}},
    "recommendation_saturation": {"recommendations": {"latency_ms": 850, "error_rate": 0.15}},
    "inventory_timeout": {"inventory": {"latency_ms": 1100, "error_rate": 0.7}},
    "pricing_errors": {"pricing": {"latency_ms": 180, "error_rate": 0.4}},
}


def _fraction(value: str) -> float:
    return int(hashlib.sha256(value.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


async def inject_fault(request: Request, service_name: str) -> None:
    latency = float(os.getenv("FAULT_LATENCY_MS", "0"))
    error_rate = float(os.getenv("FAULT_ERROR_RATE", "0"))
    scenario = request.headers.get("x-slo-scenario", "healthy")
    supplied_token = request.headers.get("x-slo-internal-token", "")
    expected_token = os.getenv("INTERNAL_REPLAY_TOKEN", "local-demo-token")
    overrides_enabled = os.getenv("ALLOW_SCENARIO_OVERRIDES", "true").lower() == "true"
    if overrides_enabled and supplied_token == expected_token:
        config: dict[str, Any] = SCENARIO_FAULTS.get(scenario, {}).get(service_name, {})
        latency = float(config.get("latency_ms", latency))
        error_rate = float(config.get("error_rate", error_rate))
    scale = float(os.getenv("LIVE_LATENCY_SCALE", "0.15"))
    if latency:
        await asyncio.sleep(min(latency * scale / 1000, 2.0))
    request_id = request.headers.get("x-request-id", "missing")
    if _fraction(f"{os.getenv('FAULT_SEED', 'slo-guardian')}:{scenario}:{service_name}:{request_id}") < error_rate:
        raise HTTPException(status_code=503, detail=f"deterministic {service_name} fault")


def internal_headers(request_id: str, scenario: str, traffic_class: str, attempt: int = 0) -> dict[str, str]:
    return {
        "x-request-id": request_id,
        "x-slo-scenario": scenario,
        "x-slo-traffic-class": traffic_class,
        "x-slo-request-class": "personalized-recommendations" if traffic_class == "optional" else "checkout",
        "x-slo-retry-attempt": str(attempt),
        "x-slo-internal-token": os.getenv("INTERNAL_REPLAY_TOKEN", "local-demo-token"),
    }

