# SLO Guardian

SLO Guardian watches distributed traces and service-level objectives, explains why a synthetic
system is approaching failure, compares safe interventions, and applies an operator-approved demo
policy before a cascading outage occurs.

The project deliberately separates three planes:

- **Deterministic control plane:** traces, SLOs, evidence, validation, simulation, ranking, and TTL enforcement.
- **Codex reasoning plane:** GPT-5.6 in the signed-in Codex session produces an evidence-citing hypothesis and exactly three typed policy candidates through the local MCP server.
- **Human approval plane:** simulation review, approval, rollback, and expiry.

Raw model output is never executed. Only a stored policy that passes Pydantic and safety validation,
is simulated, and is explicitly approved can reach the hard-coded synthetic policy adapter.

## Architecture

```text
Gateway → Checkout ┬→ Inventory       (critical)
                   ├→ Pricing         (critical)
                   └→ Recommendations (optional, fallback-capable)

Services → OpenTelemetry Collector → Jaeger → SLO Guardian control plane
```

See [docs/architecture.md](docs/architecture.md) for the full architecture decision record and
[docs/demo-script.md](docs/demo-script.md) for the three-minute walkthrough.

## Try it instantly (GitHub Codespaces)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/divya0702/slo-guardian)

No local install required. Opening a Codespace builds and starts the complete Docker Compose stack
automatically (a few minutes on first launch) and generates random local tokens for you. Once the
**Ports** tab shows port `3000` forwarded, open it for the dashboard (`8080` for the control-plane
API docs, `16686` for Jaeger).

This gives you the full deterministic demo flow: analyze an incident, refresh the recorded
recommendation, rank candidates, run bounded live replay, and approve/deactivate a policy. The
interactive GPT-5.6-through-Codex session described below still requires your own Codex sign-in,
since Codex authentication is personal and is never proxied by the application.

## Prerequisites

- Docker Desktop with Docker Compose v2 or newer.
- Approximately 4 GB of free memory for the complete stack.
- Python 3.12 and Codex signed in with ChatGPT for the interactive reasoning workflow.

No `OPENAI_API_KEY` is used by SLO Guardian.

## Quick start

1. Create the local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

   On macOS or Linux, use `cp .env.example .env`.

2. Replace both local tokens in `.env` with different random values. They authenticate only
   Compose-internal policy commands and localhost MCP submissions.

3. Build and start the stack:

   ```bash
   docker compose up --build --wait
   ```

4. Open:

   - Dashboard: http://localhost:3000
   - Jaeger: http://localhost:16686
   - Control-plane API docs: http://localhost:8080/docs
   - Synthetic gateway: http://localhost:8000/checkout?scenario=healthy

5. Select **Slow recommendations**, click **Analyze incident**, then **Rank all**, **Live replay**,
   and **Approve & activate**. The active policy automatically expires after its validated TTL.

6. Stop the stack:

   ```bash
   docker compose down
   ```

   To also delete local demo history, run `docker compose down -v`.

## GPT-5.6 through Codex and local MCP

The default dashboard mode uses scenario-specific, checked-in structured recommendations. It does
not contact OpenAI and produces repeatable policy and SLO results.

For an interactive GPT-5.6 analysis, install the local development dependencies and start a new
Codex session from this trusted repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\Activate.ps1
codex
```

On macOS or Linux, activate `.venv/bin/activate`. The checked-in `.codex/config.toml` selects
`gpt-5.6-sol` with medium reasoning and launches the `slo_guardian` stdio MCP server. Then invoke:

```text
$slo-guardian-incident-response investigate slow_dependency
```

The repo-scoped skill calls MCP tools to read the incident packet, submit exactly three structured
candidates, and run deterministic ranking. Return to the dashboard and click **Refresh MCP result**
to display that submission. The MCP toolset intentionally contains no approval or activation tool.
The operator must simulate and approve a stored policy ID in the dashboard.

Codex authentication stays in Codex and follows the user's ChatGPT access. It is never passed to the
application or MCP server. Local tokens remain environment variables; never commit `.env`.

## Scenarios

Twelve scenarios cover healthy traffic, optional dependency latency, retries, timeouts, saturation,
critical dependency failures, misleading correlations, unsafe policies, and hallucinated evidence.
Scenario files contain synthetic inputs only and live replay can target only the Compose-internal
gateway with bounded request count and concurrency.

## Tests

Run the backend and policy tests inside the pinned Python 3.12 image:

```bash
docker compose --profile test run --rm integration-tests
```

Run frontend checks locally:

```bash
cd dashboard
npm install
npm run build
npm test
```

For a host-side backend development environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
```

On macOS/Linux, activate or invoke `.venv/bin/python` instead. Windows users can run the complete
local five-process lifecycle check with `tests/run_local_e2e.ps1` after installing the dependencies.

## API workflow

1. `POST /api/v1/analyses` creates an immutable incident packet and recorded demo candidates.
2. `POST /api/v1/incidents/{id}/recommendations` accepts a token-authenticated, strict Codex MCP submission and stores validated/rejected candidates.
3. `POST /api/v1/incidents/{id}/rank` counterfactually simulates and orders all valid candidates.
4. `POST /api/v1/simulations` runs a selected counterfactual or bounded live replay.
5. `POST /api/v1/policies/{id}/approve` accepts only a stored policy in `simulated` state.
6. `POST /api/v1/policies/{id}/deactivate` rolls it back before TTL expiry.
7. `POST /api/v1/demo/reset` clears synthetic history and active demo policy state.

## Troubleshooting

- **A service is unhealthy:** run `docker compose ps` and `docker compose logs <service>`.
- **No traces in Jaeger:** wait several seconds for the Collector batch, generate a gateway request,
  and select the `gateway` service in Jaeger.
- **MCP tools are missing:** trust the repository, install `requirements-dev.txt`, activate the same virtual environment before starting Codex, and restart the Codex session.
- **MCP submission is unauthorized:** ensure `MCP_SUBMISSION_TOKEN` matches in the host `.env` and the restarted control-plane container.
- **Live replay fails:** confirm all service health checks pass and the same
  `INTERNAL_REPLAY_TOKEN` is supplied to the control plane and services.
- **Ports are occupied:** stop the conflicting application or change only the host-side port mapping.
- **Docker registry EOF:** retry the build; this indicates an interrupted image download rather than
  an application failure.

## Synthetic benchmark disclosure

Values in `sample-output/` are generated by the checked-in deterministic scenarios. They are not
production performance claims. Live replay results depend on the host and are shown separately from
counterfactual predictions.

## License

Apache-2.0. See [LICENSE](LICENSE).
