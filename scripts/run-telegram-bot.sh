#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="apps/api/src:apps/telegram-bot/src:apps/worker/src:packages/storage/src:packages/connectors/src:packages/agents/src:packages/orchestration/src:packages/llm/src:packages/runtime/src:packages/observability/src"

python -m watchfiles --filter python helm_telegram_bot.main apps/telegram-bot/src packages/
