from fastapi import FastAPI, Request

from services.common.faults import inject_fault
from services.common.telemetry import configure_telemetry

app = FastAPI(title="Recommendations Service")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "recommendations"}


@app.get("/readyz")
async def readyz():
    return {"status": "ready"}


@app.get("/recommendations/{customer_id}")
async def recommendations(customer_id: str, request: Request):
    await inject_fault(request, "recommendations")
    return {"customer_id": customer_id, "items": ["sku-2", "sku-3"], "personalized": True}


configure_telemetry(app, "recommendations")

