---
name: slo-guardian-incident-response
description: Investigate SLO Guardian OpenTelemetry incidents through the repository-local MCP server, produce exactly three structured and evidence-citing policy candidates, submit them to deterministic Pydantic and safety validation, and compare counterfactual results. Use for SLO pressure diagnosis, demo scenarios, policy safety evaluation, incident evidence review, or the hackathon GPT reasoning demonstration. Never use it to approve or activate a policy.
---

# SLO Guardian incident response

Use Codex as the reasoning plane and the `slo_guardian` MCP server as the deterministic reliability boundary.

## Workflow

1. Call `list_scenarios` when the scenario is unspecified.
2. Call `prepare_incident` once with the selected scenario and `fixture` unless the user explicitly requests collected Jaeger traces.
3. Inspect only the returned incident packet. Do not infer unseen metrics, deployments, traces, or services.
4. Read [references/recommendation-format.md](references/recommendation-format.md) before constructing the submission.
5. Form exactly three distinct candidates. Cite only evidence IDs present in the packet.
6. Call `submit_recommendation` once. Treat schema errors and rejection reasons as authoritative evidence about system safety.
7. Call `rank_candidates` when at least one candidate is validated. Use simulator measurements instead of the proposal's `expected_effect` when explaining impact.
8. Report the diagnosis, rejected candidates and reasons, deterministic ranking, uncertainty, and the safest stored policy ID.
9. Stop before approval. Direct the operator to review and approve the stored simulated policy in the dashboard.

## Safety boundary

- Never call application or service endpoints directly.
- Never construct shell commands, arbitrary URLs, headers, code, or deployment configuration from a recommendation.
- Never represent confidence as authorization.
- Never claim that submission, validation, or simulation activated a policy.
- Preserve critical checkout, inventory, and pricing traffic.
- Prefer `no_action` when the packet does not support a safe allowlisted intervention.
- Do not hide or rewrite a rejected candidate during a safety-evaluation scenario.

The MCP server intentionally has no approval or activation tool. The human-facing dashboard is the only approval surface.
