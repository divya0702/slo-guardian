from __future__ import annotations

import os
from typing import Any

import httpx


class JaegerTraceSource:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv("JAEGER_QUERY_URL", "http://jaeger:16686")

    async def fetch_spans(self, service: str = "gateway", limit: int = 100) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/api/traces", params={"service": service, "limit": min(limit, 100)}
            )
            response.raise_for_status()
        spans: list[dict[str, Any]] = []
        for trace in response.json().get("data", []):
            processes = trace.get("processes", {})
            for index, span in enumerate(trace.get("spans", [])):
                process = processes.get(span.get("processID"), {})
                tags = {item.get("key"): item.get("value") for item in span.get("tags", [])}
                if tags.get("span.kind") not in {"server", None}:
                    continue
                service_name = process.get("serviceName", service)
                if service_name not in {"gateway", "checkout", "inventory", "pricing", "recommendations"}:
                    continue
                spans.append(
                    {
                        "trace_id": trace.get("traceID", "unknown"),
                        "span_id": span.get("spanID", f"span-{index}"),
                        "service": service_name,
                        "duration_ms": round(float(span.get("duration", 0)) / 1000, 3),
                        "error": bool(tags.get("error", False)) or tags.get("http.status_code", 200) >= 500,
                        "traffic_class": tags.get("slo.traffic_class", "critical"),
                        "retry_count": int(tags.get("slo.retry_attempt", 0)),
                        "end_index": int(span.get("startTime", 0) + span.get("duration", 0)),
                    }
                )
        if not spans:
            raise ValueError("Jaeger returned no analyzable spans")
        return spans

