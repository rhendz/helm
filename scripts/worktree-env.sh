#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage:
  scripts/worktree-env.sh prepare
  scripts/worktree-env.sh link <worktree-path>
  scripts/worktree-env.sh link-self
  scripts/worktree-env.sh status [worktree-path]
USAGE
}

ensure_worktree() {
  local p="$1"
  if [[ ! -e "$p/.git" ]]; then
    echo "error: '$p' is not a git worktree"
    exit 1
  fi
}

prepare_shared() {
  cd "$ROOT_DIR"
  if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required (install: https://docs.astral.sh/uv/getting-started/installation/)"
    exit 1
  fi

  if [[ ! -d .venv ]]; then
    uv sync --frozen --extra dev
    echo "created shared .venv"
  else
    echo "shared .venv already exists"
  fi

  if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "created .env from .env.example"
  else
    echo "shared .env already exists"
  fi
}

link_shared() {
  local worktree_path="$1"
  ensure_worktree "$worktree_path"

  if [[ ! -d "$ROOT_DIR/.venv" ]]; then
    echo "error: shared .venv missing; run prepare first"
    exit 1
  fi

  ln -sfn "$ROOT_DIR/.venv" "$worktree_path/.venv"
  echo "linked: $worktree_path/.venv -> $ROOT_DIR/.venv"

  if [[ -f "$ROOT_DIR/.env" ]]; then
    ln -sfn "$ROOT_DIR/.env" "$worktree_path/.env"
    echo "linked: $worktree_path/.env -> $ROOT_DIR/.env"
  fi
}

main_worktree() {
  git worktree list --porcelain | awk '/^worktree /{print $2; exit}'
}

link_self() {
  local current
  local main
  current="$(git rev-parse --show-toplevel)"
  main="$(main_worktree)"

  if [[ -z "$main" ]]; then
    echo "error: cannot detect main worktree"
    exit 1
  fi

  ROOT_DIR="$main"
  prepare_shared

  if [[ "$current" == "$main" ]]; then
    echo "current directory is main worktree; nothing to link"
    return
  fi

  link_shared "$current"
}

status() {
  local p="${1:-$ROOT_DIR}"
  echo "main repo: $ROOT_DIR"
  [[ -d "$ROOT_DIR/.venv" ]] && echo "shared .venv: present" || echo "shared .venv: missing"
  [[ -f "$ROOT_DIR/.env" ]] && echo "shared .env: present" || echo "shared .env: missing"
  [[ -L "$p/.venv" ]] && echo "worktree .venv link: $(readlink "$p/.venv")" || echo "worktree .venv link: not linked"
  [[ -L "$p/.env" ]] && echo "worktree .env link: $(readlink "$p/.env")" || echo "worktree .env link: not linked"
}

cmd="${1:-}"
case "$cmd" in
  prepare) prepare_shared ;;
  link)
    [[ -n "${2:-}" ]] || { usage; exit 1; }
    link_shared "$2"
    ;;
  link-self) link_self ;;
  status) status "${2:-$ROOT_DIR}" ;;
  *) usage; exit 1 ;;
esac
