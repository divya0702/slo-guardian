# SLO Guardian three-minute demo

## Demo objective

Prove four things in one story:

1. Distributed traces reveal that an optional dependency is pushing checkout toward failure.
2. GPT-5.6 reasons over a normalized incident packet through the local MCP server.
3. Deterministic code validates and ranks the proposals; GPT cannot activate them.
4. Human-approved degradation restores checkout without rejecting critical traffic.

The closing line is: **GPT proposes, deterministic code decides, and the operator approves.**

## Before recording

Do this before the timer starts:

1. Start the stack and confirm it is healthy:

   ```powershell
   docker compose up -d --build --wait
   docker compose ps
   ```

2. Open three windows or tabs:

   - Dashboard: http://localhost:3000
   - Codex session started from this trusted repository
   - Jaeger: http://localhost:16686

3. Activate the repository virtual environment before starting Codex so the local MCP dependency is available.
4. Confirm `slo_guardian` appears in `codex mcp list`.
5. In the dashboard, click **Reset**, select **Slow recommendations**, and click **Analyze incident**.
6. In Codex, complete this prompt once and leave the transcript open:

   ```text
   $slo-guardian-incident-response investigate slow_dependency
   ```

7. In the transcript, leave these MCP calls visible:

   ```text
   prepare_incident
   submit_recommendation
   rank_candidates
   ```

8. Return to the dashboard and click **Refresh MCP result**. Select the top-ranked candidate shown by Codex, but do not run live replay or approve it yet.
9. Leave the slow-recommendations incident open and keep browser zoom near 90% so all four panels fit at 1920×1080.

Do not depend on a fresh model response completing during the three-minute recording. The completed Codex transcript is genuine session evidence and gives the narration a predictable pace.

Do not click **Reset** or **Analyze incident** again after the Codex run: those actions intentionally rebuild deterministic demo state. Start the recording from the prepared MCP result.

## Timed presenter script

### 0:00–0:18 — The problem and product

**Screen:** Dashboard showing the prepared slow-recommendations incident and MCP result.

**Say:**

> During an outage, traces tell us what is slow, but engineers still have to decide why it is failing and which intervention is safe. SLO Guardian combines deterministic reliability controls with GPT-5.6 incident reasoning across five instrumented services.

**Point at:** The service graph and the optional checkout-to-recommendations edge.

### 0:18–0:45 — Explain the incident

**Say:**

> Now recommendations slow down. Recommendations are optional, but checkout retries them, so the failure propagates onto the critical checkout path. The trace-derived graph shows recommendations and checkout under pressure.

**Point at:**

- Checkout p99 near `1162.96 ms`.
- Recommendations p99 near `851.22 ms`.
- Retry amplification at `3×`.
- The critical inventory and pricing branches remain protected.

**Say:**

> Each claim is represented by a stable evidence ID. The reasoning plane is not allowed to cite anything outside this packet.

### 0:45–1:20 — Show genuine GPT-5.6 reasoning

**Screen:** Switch to the prepared Codex transcript.

**Say:**

> GPT-5.6 runs through my signed-in Codex session, not through an API key embedded in the application. The repository skill asks the local MCP server for a normalized incident packet.

**Point at:** `prepare_incident` and its evidence IDs.

**Say:**

> GPT produces exactly three typed candidates and cites supplied evidence. It submits those candidates as untrusted data. The MCP server runs the same strict Pydantic schema and allowlisted safety rules used by the control plane.

**Point at:** `submit_recommendation`, validation states, and `rank_candidates`.

**Say:**

> Notice what is missing: there is no execute, approve, or activate MCP tool. GPT can diagnose, propose, and request simulation. It cannot change traffic.

### 1:20–1:48 — Compare candidates and safety

**Screen:** Return to the dashboard.

**Action:** Click **Refresh MCP result**, then briefly select each candidate.

**Say:**

> The dashboard now shows the stored MCP submission. Every candidate has a server-generated policy ID. Unknown evidence, arbitrary fields, unsafe targets, invalid thresholds, or attempts to shed critical traffic are rejected and remain visible with explicit reasons.

**Action:** Click **Rank all**.

**Say:**

> The model does not choose the winner. Deterministic counterfactual replay ranks candidates lexicographically, starting with zero critical checkout rejection and critical success rate.

**Point at:** The selected top-ranked candidate and the green critical-traffic safety result.

### 1:48–2:22 — Measure before applying

**Action:** Click **Live replay**.

**Say:**

> Before approval, SLO Guardian installs the candidate only inside an isolated synthetic replay. Request count, concurrency, retries, timeouts, and the target gateway are all bounded. Caller-provided URLs are never accepted.

**Point at:** Current versus observed metrics.

**Say:**

> In this synthetic run, checkout improves while critical rejected requests remain zero. The optional experience degrades, but checkout remains available. These measured simulator results replace the model's untrusted impact estimate.

If using the deterministic sample output, the expected comparison is:

- Current checkout p99: `1162.96 ms`.
- Fallback counterfactual p99: `382.0 ms`.
- Critical requests rejected: `0`.
- Optional degradation: `100%` while the fallback is active.

Label these numbers as synthetic; do not describe them as production performance.

### 2:22–2:48 — Human approval and recovery

**Action:** Click **Approve & activate**.

**Say:**

> Only now does the human approve a stored, validated, simulated policy ID. The control plane converts it through a hard-coded dispatch table into a typed internal command. No model-generated code, URL, header, or shell command crosses this boundary.

**Point at:** Active policy ID and automatic TTL rollback.

**Say:**

> The policy applies only to synthetic Compose traffic and expires automatically. Critical checkout, inventory, and pricing traffic is never shed.

### 2:48–3:00 — Close

**Action:** Optionally click **Deactivate**, or point at the TTL message.

**Say:**

> SLO Guardian turns observability into a safe decision workflow: traces provide evidence, GPT-5.6 explains and proposes, deterministic simulation measures, and a human authorizes. GPT proposes, deterministic code decides, and the operator approves.

## Exact Codex prompt for the demo

Use the skill explicitly so its workflow is visible in the transcript:

```text
$slo-guardian-incident-response investigate slow_dependency.
Use only evidence in the incident packet, submit exactly three distinct candidates,
show all validation results, rank every valid candidate, and stop before approval.
```

Do not ask Codex to activate or apply the result. The skill and MCP server intentionally stop at ranking.

## Thirty-second backup version

If time is cut short, say:

> Recommendations slowed down, retries amplified to three calls per checkout, and checkout p99 breached its SLO. GPT-5.6 used the local MCP server to cite this packet and propose three typed policies. Deterministic validation and replay selected the safest stored candidate with zero critical rejections. GPT has no activation tool, so only the operator can approve the TTL-bound synthetic policy.

## Failure-safe presenter lines

- **Codex is still reasoning:** “The model is intentionally outside the application request path. I have the completed session here, and deterministic demo mode remains available without any model dependency.”
- **A candidate is rejected:** “That is expected behavior—the validator is proving the boundary, and rejected output stays visible rather than being silently repaired.”
- **Live replay varies slightly:** “Live timing varies by host; the deterministic counterfactual is the acceptance oracle, and both results are labeled separately.”
- **Jaeger has not populated yet:** “The deterministic fixture adapter uses the same normalized span contract, so the SLO, evidence, validation, and simulation pipeline remains reproducible.”
- **Approval is disabled:** “Approval requires a stored candidate to reach the simulated state first. The state machine is enforcing the workflow.”

## Likely judge questions

### Why use GPT here?

GPT correlates the service graph, SLO pressure, retry behavior, changes, and alternative hypotheses into a concise incident explanation and several interventions. Threshold calculation, validation, ranking, and enforcement stay deterministic.

### Why not let GPT execute the policy?

Recommendations are probabilistic and may contain unsafe or hallucinated fields. SLO Guardian treats them as untrusted proposals, validates evidence and actions, measures them, and requires human approval.

### Why MCP instead of an OpenAI API call?

The application remains a local developer tool with no model credential. GPT-5.6 runs through the operator's signed-in Codex access, while the local MCP server exposes narrow reliability capabilities and contains no activation tool.

### Could this protect production traffic?

Not in the MVP. Enforcement is deliberately limited to synthetic Docker Compose traffic. Production adapters, authentication, RBAC, and Kubernetes integration are roadmap items.

### Are the improvement numbers real?

They are measured deterministic synthetic results, not production claims. SLO Guardian displays counterfactual and observed replay values separately.

## Session evidence

Keep the Codex transcript showing the selected GPT-5.6 model, skill invocation, MCP calls, structured submission, validation results, and deterministic ranking. Codex `/feedback` opens the product feedback dialog and may include logs; it is not the mechanism that executes or approves a SLO Guardian policy.
