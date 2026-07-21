from fastapi import FastAPI, Request

from services.common.faults import inject_fault
from services.common.telemetry import configure_telemetry

app = FastAPI(title="Inventory Service")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "inventory"}


@app.get("/readyz")
async def readyz():
    return {"status": "ready"}


@app.get("/inventory/{sku}")
async def inventory(sku: str, request: Request):
    await inject_fault(request, "inventory")
    return {"sku": sku, "available": True, "quantity": 42}


configure_telemetry(app, "inventory")

