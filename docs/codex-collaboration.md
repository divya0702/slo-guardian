# Codex collaboration record

The build is organized as independently verifiable phases: architecture, services, telemetry,
SLO calculation, policy safety, local MCP integration, simulation, approval, dashboard, and
end-to-end verification.

## Interactive reasoning session

1. Start Docker Compose and activate the repository virtual environment.
2. Start Codex from the trusted repository so `.codex/config.toml` loads `gpt-5.6-sol`, medium
   reasoning, and the `slo_guardian` MCP server.
3. Invoke `$slo-guardian-incident-response investigate slow_dependency`.
4. Retain the tool transcript showing `prepare_incident`, `submit_recommendation`, and
   `rank_candidates`. It demonstrates GPT reasoning while validation remains deterministic.
5. Refresh the dashboard, inspect stored policy IDs, and perform human approval there.

The Codex `/feedback` command opens its feedback dialog and can optionally include logs; it is not
an application execution mechanism. Keep any required session evidence according to the event's
submission instructions. Never include tokens or copied private incident data.
