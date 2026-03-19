#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="apps/api/src:apps/worker/src:apps/telegram-bot/src::packages/storage/src:packages/connectors/src:packages/agents/src:packages/orchestration/src:packages/llm/src:packages/runtime/src:packages/observability/src"

if command -v uv >/dev/null 2>&1; then
  uv run --frozen --extra dev alembic upgrade head
else
  alembic upgrade head
fi

# Seed bootstrap user from env vars (idempotent)
if command -v uv >/dev/null 2>&1; then
  uv run --frozen --extra dev python -c "from helm_storage.bootstrap import run_bootstrap; run_bootstrap()"
else
  python -c "from helm_storage.bootstrap import run_bootstrap; run_bootstrap()"
fi
