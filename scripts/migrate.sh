#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  uv run --frozen --extra dev alembic upgrade head
else
  python -m alembic upgrade head
fi
