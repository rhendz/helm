#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="apps/api/src:packages/domain/src:packages/storage/src:packages/connectors/src:packages/agents/src:packages/orchestration/src:packages/llm/src:packages/observability/src"
uvicorn helm_api.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}" --reload
