#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="apps/api/src:apps/worker/src:apps/telegram-bot/src:packages/storage/src:packages/connectors/src:packages/agents/src:packages/orchestration/src:packages/llm/src:packages/runtime/src:packages/observability/src"

python -m watchfiles --filter python helm_worker.main apps/worker/src packages/
