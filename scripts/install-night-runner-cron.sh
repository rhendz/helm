#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNNER_CMD="cd \"$REPO_ROOT\" && bash ./scripts/night-runner.sh"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 1 * * *}"
CRON_TAG="# codex-night-runner"
CRON_LINE="$CRON_SCHEDULE $RUNNER_CMD $CRON_TAG"
DRY_RUN=0
MODE="install"

usage() {
  cat <<'EOF'
Usage: scripts/install-night-runner-cron.sh [--remove] [--dry-run] [--help]

Fallback scheduler management for night runner cron entry.
Codex Automation is the preferred scheduler.

Options:
  --remove    Remove existing night runner cron entry.
  --dry-run   Print intended crontab changes only.
  --help      Show this help message.

Environment variables:
  CRON_SCHEDULE   Cron expression to install (default: "0 1 * * *")
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove)
      MODE="remove"
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
FILTERED_CRON="$(printf '%s\n' "$CURRENT_CRON" | sed "/$CRON_TAG/d")"

if [[ "$MODE" == "remove" ]]; then
  NEW_CRON="$FILTERED_CRON"
else
  if printf '%s\n' "$CURRENT_CRON" | grep -Fq "$CRON_TAG"; then
    NEW_CRON="$FILTERED_CRON"$'\n'"$CRON_LINE"
  else
    if [[ -n "$FILTERED_CRON" ]]; then
      NEW_CRON="$FILTERED_CRON"$'\n'"$CRON_LINE"
    else
      NEW_CRON="$CRON_LINE"
    fi
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "DRY RUN"
  echo "Mode: $MODE"
  echo "CRON_SCHEDULE: $CRON_SCHEDULE"
  echo "Entry tag: $CRON_TAG"
  echo "Resulting crontab:"
  printf '%s\n' "$NEW_CRON"
  exit 0
fi

if [[ -n "$NEW_CRON" ]]; then
  printf '%s\n' "$NEW_CRON" | crontab -
else
  crontab -r 2>/dev/null || true
fi

if [[ "$MODE" == "remove" ]]; then
  echo "Removed fallback night runner cron entry (if present)."
else
  echo "Installed/updated fallback night runner cron entry:"
  echo "$CRON_LINE"
fi
