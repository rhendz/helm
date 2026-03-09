#!/usr/bin/env bash
set -euo pipefail

uv run --frozen --extra dev pytest
