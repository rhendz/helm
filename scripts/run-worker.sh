#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="apps/worker/src:apps/telegram-bot/src:packages/domain/src:packages/storage/src:packages/connectors/src:packages/agents/src:packages/orchestration/src:packages/llm/src:packages/runtime/src:packages/observability/src"

python -m helm_worker.main
