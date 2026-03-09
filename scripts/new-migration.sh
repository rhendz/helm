#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/new-migration.sh \"message\""
  exit 1
fi

export PYTHONPATH="apps/api/src:apps/worker/src:apps/telegram-bot/src:packages/domain/src:packages/storage/src:packages/connectors/src:packages/agents/src:packages/orchestration/src:packages/llm/src:packages/observability/src"
alembic revision --autogenerate -m "$1"
