#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="apps/api/src:apps/worker/src:apps/telegram-bot/src:packages/storage/src:packages/agents/src:packages/orchestration/src:packages/llm/src:packages/runtime/src:packages/observability/src:packages/providers/src"

python -m watchfiles --filter python helm_worker.main.run apps/worker/src packages/
