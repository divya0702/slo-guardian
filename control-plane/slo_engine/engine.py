from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from api.schemas import PressureStatus, ServiceSLO


DEFAULT_THRESHOLDS_MS = {
    "gateway": 1000.0,
    "checkout": 1000.0,
    "inventory": 300.0,
    "pricing": 300.0,
    "recommendations": 300.0,
}


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return round(ordered[index], 2)


def calculate_slos(
    spans: list[dict[str, Any]],
    objective: float = 0.99,
    minimum_samples: int = 20,
) -> dict[str, ServiceSLO]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for span in sorted(spans, key=lambda item: (item["end_index"], item["trace_id"], item["span_id"])):
        grouped[span["service"]].append(span)

    results: dict[str, ServiceSLO] = {}
    for service, service_spans in sorted(grouped.items()):
        window = service_spans[-100:]
        count = len(window)
        durations = [float(item["duration_ms"]) for item in window]
        errors = sum(bool(item["error"]) for item in window)
        latency_bad = sum(value > DEFAULT_THRESHOLDS_MS[service] for value in durations)
        allowed_bad = max(count * (1 - objective), 1e-9)
        availability_consumption = errors / allowed_bad
        latency_consumption = latency_bad / allowed_bad
        pressure = max(availability_consumption, latency_consumption)
        if count < minimum_samples:
            status = PressureStatus.insufficient_data
        elif pressure < 0.5:
            status = PressureStatus.healthy
        elif pressure < 1.0:
            status = PressureStatus.warning
        else:
            status = PressureStatus.breached
        retry_amp = 1 + (
            sum(int(item.get("retry_count", 0)) for item in window) / count if count else 0
        )
        dependency_contribution = (
            percentile(durations, 0.99) if service in {"inventory", "pricing", "recommendations"} else 0
        )
        results[service] = ServiceSLO(
            service=service,
            sample_count=count,
            availability=round(1 - errors / count, 4) if count else 0,
            error_rate=round(errors / count, 4) if count else 0,
            p50_ms=percentile(durations, 0.50),
            p95_ms=percentile(durations, 0.95),
            p99_ms=percentile(durations, 0.99),
            request_volume=count,
            retry_amplification=round(retry_amp, 2),
            dependency_contribution_ms=dependency_contribution,
            availability_budget_remaining_percent=round(max(0, 100 * (1 - availability_consumption)), 2),
            latency_budget_remaining_percent=round(max(0, 100 * (1 - latency_consumption)), 2),
            pressure=round(pressure, 2),
            status=status,
        )
    return results

