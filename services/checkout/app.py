from __future__ import annotations

import asyncio
import hashlib
import os
import time
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from services.common.faults import inject_fault, internal_headers
from services.common.telemetry import configure_telemetry

app = FastAPI(title="Checkout Service")
_active_policy: dict[str, Any] | None = None
_rate_window = {"second": 0, "count": 0}


class InternalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_id: str
    action_type: Literal[
        "shed_optional_traffic", "rate_limit", "disable_retries", "serve_fallback", "no_action"
    ]
    parameters: dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: int = Field(ge=30, le=600)


def _authorize(token: str | None) -> None:
    if token != os.getenv("INTERNAL_REPLAY_TOKEN", "local-demo-token"):
        raise HTTPException(status_code=403, detail="invalid internal token")


def _policy() -> dict[str, Any] | None:
    global _active_policy
    if _active_policy and time.time() >= _active_policy["expires_epoch"]:
        _active_policy = None
    return _active_policy


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "checkout"}


@app.get("/readyz")
async def readyz():
    return {"status": "ready"}


@app.post("/internal/policy")
async def install_policy(policy: InternalPolicy, x_slo_internal_token: str | None = Header(default=None)):
    global _active_policy
    _authorize(x_slo_internal_token)
    allowed_parameters = {
        "shed_optional_traffic": {"percentage", "fallback_id"},
        "rate_limit": {"requests_per_second", "burst"},
        "disable_retries": {"edge"},
        "serve_fallback": {"fallback_id"},
        "no_action": set(),
    }
    if set(policy.parameters) - allowed_parameters[policy.action_type]:
        raise HTTPException(status_code=422, detail="unknown policy parameter")
    now = time.time()
    _active_policy = {
        **policy.model_dump(),
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "expires_epoch": now + policy.ttl_seconds,
        "expires_at": datetime.fromtimestamp(now + policy.ttl_seconds, timezone.utc).isoformat(),
    }
    return _active_policy


@app.delete("/internal/policy")
async def remove_policy(x_slo_internal_token: str | None = Header(default=None)):
    global _active_policy
    _authorize(x_slo_internal_token)
    _active_policy = None
    return {"status": "inactive"}


@app.get("/internal/policy")
async def active_policy(x_slo_internal_token: str | None = Header(default=None)):
    _authorize(x_slo_internal_token)
    return _policy() or {"status": "inactive"}


def _should_shed(request_id: str, percentage: int) -> bool:
    value = int(hashlib.sha256(f"shed:{request_id}".encode()).hexdigest()[:8], 16) % 100
    return value < percentage


def _rate_limited(requests_per_second: int, burst: int) -> bool:
    now_second = int(time.time())
    if _rate_window["second"] != now_second:
        _rate_window.update({"second": now_second, "count": 0})
    _rate_window["count"] += 1
    return _rate_window["count"] > max(requests_per_second, burst)


async def _critical_dependency(url: str, headers: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


async def _optional_recommendations(
    customer_id: str, request_id: str, scenario: str
) -> tuple[dict[str, Any], bool, int]:
    policy = _policy()
    fallback = {"items": ["popular-1", "popular-2"], "personalized": False}
    if policy:
        action = policy["action_type"]
        parameters = policy["parameters"]
        if action == "serve_fallback":
            return fallback, True, 0
        if action == "shed_optional_traffic" and _should_shed(
            request_id, int(parameters["percentage"])
        ):
            return fallback, True, 0
        if action == "rate_limit" and _rate_limited(
            int(parameters["requests_per_second"]), int(parameters["burst"])
        ):
            return fallback, True, 0

    scenario_attempts = {
        "slow_dependency": 3,
        "retry_storm": 4,
        "recommendation_timeout": 2,
        "recommendation_saturation": 3,
        "checkout_pool_exhaustion": 4,
        "unsafe_policy": 3,
        "hallucinated_evidence": 3,
    }
    attempts = scenario_attempts.get(scenario, 1)
    if policy and policy["action_type"] == "disable_retries":
        attempts = 1

    url = f"{os.getenv('RECOMMENDATIONS_URL', 'http://recommendations:8000')}/recommendations/{customer_id}"
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.get(
                    url, headers=internal_headers(request_id, scenario, "optional", attempt)
                )
                response.raise_for_status()
                return response.json(), False, attempt + 1
        except httpx.HTTPError:
            if attempt + 1 == attempts:
                return fallback, True, attempts
    return fallback, True, attempts


@app.get("/checkout")
async def checkout(request: Request, customer_id: str = "demo"):
    await inject_fault(request, "checkout")
    request_id = request.headers.get("x-request-id", "missing")
    scenario = request.headers.get("x-slo-scenario", "healthy")
    critical_headers = internal_headers(request_id, scenario, "critical")
    inventory_url = f"{os.getenv('INVENTORY_URL', 'http://inventory:8000')}/inventory/sku-1"
    pricing_url = f"{os.getenv('PRICING_URL', 'http://pricing:8000')}/prices/sku-1"
    try:
        inventory, price = await asyncio.gather(
            _critical_dependency(inventory_url, critical_headers),
            _critical_dependency(pricing_url, critical_headers),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="critical checkout dependency unavailable") from exc
    recommendations, used_fallback, attempts = await _optional_recommendations(
        customer_id, request_id, scenario
    )
    return {
        "order_ready": True,
        "inventory": inventory,
        "price": price,
        "recommendations": recommendations,
        "recommendation_fallback": used_fallback,
        "recommendation_attempts": attempts,
        "active_policy_id": _policy()["policy_id"] if _policy() else None,
    }


configure_telemetry(app, "checkout")

