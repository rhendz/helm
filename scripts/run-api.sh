#!/usr/bin/env bash
set -euo pipefail

python -m uvicorn helm_api.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}" --reload
