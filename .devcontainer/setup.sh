#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^INTERNAL_REPLAY_TOKEN=.*/INTERNAL_REPLAY_TOKEN=$(openssl rand -hex 16)/" .env
  sed -i "s/^MCP_SUBMISSION_TOKEN=.*/MCP_SUBMISSION_TOKEN=$(openssl rand -hex 16)/" .env
  echo "Generated .env with random local tokens."
fi

docker compose up --build --wait

echo ""
echo "SLO Guardian is running. Use the Ports tab to open:"
echo "  3000  - dashboard"
echo "  8080  - control-plane API docs (/docs)"
echo "  16686 - Jaeger"
