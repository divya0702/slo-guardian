# Recommendation submission format

Submit one object with this shape:

```json
{
  "summary": "Evidence-backed incident summary.",
  "suspected_root_cause": "Most likely cause supported by cited evidence.",
  "evidence_ids": ["ev_known_id"],
  "alternative_hypotheses": ["Alternative explanation [ev_known_id]."],
  "candidates": [
    {
      "title": "Short candidate title",
      "target": {
        "service": "checkout",
        "route": "/dependencies/recommendations",
        "traffic_class": "optional"
      },
      "conditions": [
        {"metric": "p99_latency_ms", "operator": "gt", "value": 300}
      ],
      "action": {"type": "serve_fallback", "fallback_id": "static-recommendations"},
      "ttl_seconds": 300,
      "evidence_ids": ["ev_known_id"],
      "expected_effect": "Untrusted hypothesis; simulation replaces this estimate."
    }
  ],
  "risks": ["Personalization is reduced [ev_known_id]."],
  "uncertainty": "What the packet cannot establish.",
  "confidence": 0.8
}
```

## Exact constraints

- Provide exactly three candidates.
- Use condition metrics `p99_latency_ms`, `error_budget_remaining_percent`, `error_rate`, or `retry_amplification`.
- Use operators `gt`, `gte`, `lt`, or `lte`.
- Set TTL from 30 through 600 seconds.
- Use only packet evidence IDs in the recommendation and every candidate.
- Use only packet `allowed_actions`.
- Set `target` to `null` for `no_action`.
- Use only `checkout -> /dependencies/recommendations -> optional` for `disable_retries`.
- Use only `static-recommendations` or `empty-recommendations` as fallback IDs.
- Never shed or rate-limit critical traffic.

Allowed action shapes:

```json
{"type":"shed_optional_traffic","percentage":50,"fallback_id":"static-recommendations"}
{"type":"rate_limit","requests_per_second":50,"burst":100}
{"type":"disable_retries","edge":"checkout->recommendations"}
{"type":"serve_fallback","fallback_id":"static-recommendations"}
{"type":"no_action"}
```
