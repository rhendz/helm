#!/usr/bin/env bash
set -euo pipefail

missing=0
for cmd in python3 docker; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "missing command: $cmd"
    missing=1
  fi
done

if [[ ! -f .env ]]; then
  echo "missing .env (copy from .env.example)"
  missing=1
fi

if [[ $missing -eq 1 ]]; then
  exit 1
fi

echo "doctor check passed"
