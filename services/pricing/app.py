from fastapi import FastAPI, Request

from services.common.faults import inject_fault
from services.common.telemetry import configure_telemetry

app = FastAPI(title="Pricing Service")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "pricing"}


@app.get("/readyz")
async def readyz():
    return {"status": "ready"}


@app.get("/prices/{sku}")
async def price(sku: str, request: Request):
    await inject_fault(request, "pricing")
    return {"sku": sku, "currency": "USD", "amount": 49.0}


configure_telemetry(app, "pricing")

