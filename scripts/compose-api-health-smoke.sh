#!/usr/bin/env bash
set -euo pipefail

# Ensure compose env_file exists in CI and local ephemeral environments.
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

export APP_ENV="${APP_ENV:-ci}"
export API_PORT="${API_PORT:-8000}"

docker compose up --build -d --wait postgres
docker compose up --build -d migrate api

# Keep the probe deterministic and bounded even if compose health gate passes.
for attempt in {1..20}; do
  if curl --fail --silent --show-error "http://127.0.0.1:${API_PORT}/healthz" >/dev/null; then
    exit 0
  fi
  sleep 2
done

echo "API health check failed after retries" >&2
exit 1
