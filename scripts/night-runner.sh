#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DEFAULT_PROMPT_FILE="$REPO_ROOT/docs/archive/night-runner-prompt.md"
PROMPT_FILE="${PROMPT_FILE:-$DEFAULT_PROMPT_FILE}"
MAX_HOURS_PER_RUN="${MAX_HOURS_PER_RUN:-6}"
LOCK_DIR="$REPO_ROOT/.night-runner.lock"
LOG_DIR="$REPO_ROOT/.night-runner-logs"
REQUIRE_MAIN_BRANCH="${REQUIRE_MAIN_BRANCH:-1}"
REQUIRE_CLEAN_TREE="${REQUIRE_CLEAN_TREE:-1}"
ENABLE_LINEAR_RECONCILE="${ENABLE_LINEAR_RECONCILE:-1}"
LINEAR_RECONCILE_SINCE_DAYS="${LINEAR_RECONCILE_SINCE_DAYS:-14}"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/night-runner.sh [--dry-run] [--help]

Runs the Codex night runner prompt with lock protection and timeout.

Options:
  --dry-run   Print resolved config and command, then exit.
  --help      Show this help message.

Environment variables:
  PROMPT_FILE         Prompt file path (default: docs/archive/night-runner-prompt.md)
  MAX_HOURS_PER_RUN   Run timeout in hours (default: 6)
  REQUIRE_MAIN_BRANCH Require current branch to be main before start (default: 1)
  REQUIRE_CLEAN_TREE  Require clean git tree before start (default: 1)
  ENABLE_LINEAR_RECONCILE Run PR-to-Linear reconciliation after run (default: 1)
  LINEAR_RECONCILE_SINCE_DAYS Lookback window for reconciliation (default: 14)
EOF
}

cleanup() {
  rm -rf "$LOCK_DIR"
  if [[ -n "${WATCHDOG_PID:-}" ]]; then
    kill "$WATCHDOG_PID" >/dev/null 2>&1 || true
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      usage
      exit 0
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! [[ "$MAX_HOURS_PER_RUN" =~ ^[0-9]+$ ]] || [[ "$MAX_HOURS_PER_RUN" -lt 1 ]]; then
  echo "MAX_HOURS_PER_RUN must be a positive integer; got: $MAX_HOURS_PER_RUN" >&2
  exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

if [[ "$REQUIRE_MAIN_BRANCH" == "1" ]]; then
  CURRENT_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
  if [[ "$CURRENT_BRANCH" == "HEAD" ]]; then
    if git -C "$REPO_ROOT" branch --contains HEAD --format='%(refname:short)' | grep -qx "main"; then
      echo "Night runner running from detached HEAD that is contained in 'main'; proceeding."
    else
      echo "Night runner must start from branch 'main'; current state is detached HEAD not contained in 'main'" >&2
      exit 1
    fi
  elif [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "Night runner must start from branch 'main'; current branch is '$CURRENT_BRANCH'" >&2
    exit 1
  fi
fi

if [[ "$REQUIRE_CLEAN_TREE" == "1" ]]; then
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
    echo "Night runner requires a clean working tree before start." >&2
    exit 1
  fi
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Night runner already active; lock exists at $LOCK_DIR"
  exit 0
fi

trap cleanup EXIT INT TERM

mkdir -p "$LOG_DIR"
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
LOG_FILE="$LOG_DIR/night-runner-$TIMESTAMP.log"
TIMEOUT_SECONDS=$((MAX_HOURS_PER_RUN * 3600))

CMD=(codex exec --cd "$REPO_ROOT" --dangerously-bypass-approvals-and-sandbox -)

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "DRY RUN"
  echo "REPO_ROOT=$REPO_ROOT"
  echo "PROMPT_FILE=$PROMPT_FILE"
  echo "MAX_HOURS_PER_RUN=$MAX_HOURS_PER_RUN"
  echo "TIMEOUT_SECONDS=$TIMEOUT_SECONDS"
  echo "LOG_FILE=$LOG_FILE"
  echo "ENABLE_LINEAR_RECONCILE=$ENABLE_LINEAR_RECONCILE"
  echo "LINEAR_RECONCILE_SINCE_DAYS=$LINEAR_RECONCILE_SINCE_DAYS"
  echo "COMMAND: ${CMD[*]} < \"$PROMPT_FILE\" | tee \"$LOG_FILE\""
  exit 0
fi

echo "Starting night runner"
echo "Prompt: $PROMPT_FILE"
echo "Log: $LOG_FILE"
echo "Timeout: ${MAX_HOURS_PER_RUN}h"

set +e
("${CMD[@]}" < "$PROMPT_FILE") 2>&1 | tee "$LOG_FILE" &
RUNNER_PID=$!

(
  sleep "$TIMEOUT_SECONDS"
  if kill -0 "$RUNNER_PID" >/dev/null 2>&1; then
    echo "Timeout reached (${MAX_HOURS_PER_RUN}h); stopping process $RUNNER_PID" | tee -a "$LOG_FILE"
    kill "$RUNNER_PID" >/dev/null 2>&1 || true
  fi
) &
WATCHDOG_PID=$!

wait "$RUNNER_PID"
RUN_STATUS=$?
set -e

kill "$WATCHDOG_PID" >/dev/null 2>&1 || true

if [[ "$ENABLE_LINEAR_RECONCILE" == "1" ]]; then
  echo "Running PR-to-Linear reconciliation (since ${LINEAR_RECONCILE_SINCE_DAYS} days)" | tee -a "$LOG_FILE"
  if ! python3 "$REPO_ROOT/scripts/pr_linear_reconcile.py" \
    --team "${LINEAR_TEAM_KEY:-HELM}" \
    --since-days "$LINEAR_RECONCILE_SINCE_DAYS" | tee -a "$LOG_FILE"; then
    echo "Reconciliation step failed (non-fatal). Review setup for gh/Linear auth." | tee -a "$LOG_FILE"
  fi
fi

if [[ "$RUN_STATUS" -ne 0 ]]; then
  echo "Night runner exited with status $RUN_STATUS. See log: $LOG_FILE" >&2
  exit "$RUN_STATUS"
fi

echo "Night runner finished successfully. Log: $LOG_FILE"
