#!/usr/bin/env bash
# Start the API temporarily and exercise it with the supplied sample payload.
set -euo pipefail

project_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
port="${PORT:-8000}"
cd "$project_directory"

python -m uvicorn api:app --host 127.0.0.1 --port "$port" >/tmp/score-my-recipe-api.log 2>&1 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT

for _ in {1..20}; do
  if curl --silent --fail "http://127.0.0.1:$port/health" >/dev/null; then
    break
  fi
  sleep 0.25
done

echo '--- Health ---'
curl --silent --fail "http://127.0.0.1:$port/health"
echo
echo '--- Recipe scan ---'
curl --silent --fail --request POST "http://127.0.0.1:$port/scan-recipe" \
  --header 'Content-Type: application/json' \
  --data @tests/payloads/scan_recipe.json
echo
