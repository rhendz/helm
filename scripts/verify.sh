#!/usr/bin/env bash
set -euo pipefail

bash scripts/lint.sh
bash scripts/test.sh
