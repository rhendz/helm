#!/usr/bin/env bash
set -euo pipefail

uv run --frozen --extra dev ruff check --fix .
uv run --frozen --extra dev ruff format .
