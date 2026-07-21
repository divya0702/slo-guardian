from __future__ import annotations

import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Query, Request

from services.common.faults import inject_fault, internal_headers
from services.common.telemetry import configure_telemetry

app = FastAPI(title="SLO Guardian Gateway")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "gateway"}


@app.get("/readyz")
async def readyz():
    return {"status": "ready"}


@app.get("/checkout")
async def checkout(request: Request, scenario: str = Query(default="healthy"), customer_id: str = "demo"):
    await inject_fault(request, "gateway")
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(
                f"{os.getenv('CHECKOUT_URL', 'http://checkout:8000')}/checkout",
                params={"customer_id": customer_id},
                headers=internal_headers(request_id, scenario, "critical"),
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="checkout unavailable") from exc
    return response.json()


configure_telemetry(app, "gateway")

