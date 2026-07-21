from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SERVICES = ("gateway", "checkout", "inventory", "pricing", "recommendations")


def load_scenario(scenario_id: str, directory: str) -> dict[str, Any]:
    if not scenario_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("invalid scenario ID")
    path = Path(directory) / f"{scenario_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"unknown scenario: {scenario_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("id") != scenario_id:
        raise ValueError("scenario ID does not match file")
    return data


def _fraction(seed: str) -> float:
    value = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    return value / 0xFFFFFFFF


def build_fixture_spans(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    count = min(int(scenario.get("request_count", 100)), 100)
    retry_count = int(scenario.get("recommendation_retries", 0))
    for index in range(count):
        trace_id = hashlib.sha256(f"{scenario['id']}:{index}".encode()).hexdigest()[:32]
        for service in SERVICES:
            base = float(scenario.get("latency_ms", {}).get(service, 20))
            # Stable +/- 4% variation keeps percentile examples realistic and repeatable.
            duration = base * (0.96 + _fraction(f"{trace_id}:{service}:latency") * 0.08)
            error_rate = float(scenario.get("error_rate", {}).get(service, 0))
            is_error = _fraction(f"{trace_id}:{service}:error") < error_rate
            spans.append(
                {
                    "trace_id": trace_id,
                    "span_id": hashlib.sha256(f"{trace_id}:{service}".encode()).hexdigest()[:16],
                    "service": service,
                    "duration_ms": round(duration, 3),
                    "error": is_error,
                    "traffic_class": "optional" if service == "recommendations" else "critical",
                    "retry_count": retry_count if service == "recommendations" else 0,
                    "end_index": index,
                }
            )
    return spans

