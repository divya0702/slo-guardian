# Three-minute demo

1. Start the stack and open the dashboard and Jaeger.
2. Run **Healthy** to establish a green baseline.
3. Run **Slow dependency**. Show recommendation latency, retries, checkout p99, and linked evidence.
4. In the signed-in Codex session invoke `$slo-guardian-incident-response investigate slow_dependency`.
5. Show the MCP transcript: packet evidence, three structured candidates, validation, and ranking.
6. Click **Refresh MCP result** in the dashboard and compare accepted and rejected stored candidates.
7. Run bounded live replay for the safest candidate, then approve its stored policy ID.
8. Show checkout recovery and zero rejected critical requests, then deactivate or wait for TTL.

Close by showing that the application has no OpenAI key and the MCP server exposes no activation
tool. GPT proposed untrusted data; deterministic code and the operator controlled every transition.
