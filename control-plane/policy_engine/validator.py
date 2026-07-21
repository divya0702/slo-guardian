from __future__ import annotations

from api.schemas import PolicyProposal


ROUTES: dict[str, set[str]] = {
    "gateway": {"/checkout"},
    "checkout": {"/checkout", "/dependencies/recommendations"},
    "inventory": {"/inventory/{sku}"},
    "pricing": {"/prices/{sku}"},
    "recommendations": {"/recommendations/{customer_id}"},
}
OPTIONAL_TARGETS = {
    ("checkout", "/dependencies/recommendations"),
    ("recommendations", "/recommendations/{customer_id}"),
}


def validate_policy(proposal: PolicyProposal, evidence_ids: set[str]) -> list[str]:
    reasons: list[str] = []
    action_type = proposal.action.type

    missing = sorted(set(proposal.evidence_ids) - evidence_ids)
    if missing:
        reasons.append(f"unknown evidence IDs: {', '.join(missing)}")

    if action_type == "no_action":
        if proposal.target is not None:
            reasons.append("no_action must not specify a target")
        return reasons

    if proposal.target is None:
        reasons.append("action requires an exact target")
        return reasons

    target = proposal.target
    if target.route not in ROUTES.get(target.service, set()):
        reasons.append("target route is not registered for service")

    if action_type in {"shed_optional_traffic", "rate_limit"}:
        if target.traffic_class != "optional":
            reasons.append("critical or background traffic cannot be shed or rate limited")
        if (target.service, target.route) not in OPTIONAL_TARGETS:
            reasons.append("shedding and rate limiting are restricted to optional recommendation paths")

    if action_type == "disable_retries":
        if (target.service, target.route) != ("checkout", "/dependencies/recommendations"):
            reasons.append("retry changes are restricted to checkout->recommendations")
        if target.traffic_class != "optional":
            reasons.append("retry changes must target the optional recommendation edge")

    if action_type == "serve_fallback":
        if (target.service, target.route) not in OPTIONAL_TARGETS:
            reasons.append("fallbacks are restricted to recommendation paths")
        if target.traffic_class != "optional":
            reasons.append("fallbacks may only replace optional traffic")

    return reasons

