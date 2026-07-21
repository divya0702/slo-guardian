from __future__ import annotations

import os

from fastapi import FastAPI, Request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_client_instrumented = False


def configure_telemetry(app: FastAPI, service_name: str) -> None:
    global _client_instrumented
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    if not _client_instrumented:
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        _client_instrumented = True

    @app.middleware("http")
    async def add_slo_attributes(request: Request, call_next):
        span = trace.get_current_span()
        traffic_class = request.headers.get("x-slo-traffic-class", "critical")
        span.set_attribute("slo.traffic_class", traffic_class)
        span.set_attribute("slo.request_class", request.headers.get("x-slo-request-class", "checkout"))
        span.set_attribute("slo.scenario_id", request.headers.get("x-slo-scenario", "healthy"))
        span.set_attribute("slo.retry_attempt", int(request.headers.get("x-slo-retry-attempt", "0")))
        response = await call_next(request)
        span.set_attribute("slo.fallback", response.headers.get("x-slo-fallback", "false") == "true")
        return response

