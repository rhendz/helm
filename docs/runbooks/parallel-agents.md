# Parallel Agents Runbook

## Goal

Let multiple Codex agents run in parallel with minimal environment/setup churn.

## 1. Create worktrees

```bash
git checkout main
git pull --ff-only

git worktree add ../helm-storage -b codex/storage-main main
git worktree add ../helm-telegram -b codex/telegram-main main
git worktree add ../helm-worker -b codex/worker-main main
```

## 2. Share environment across worktrees

Run once in the main repo:

```bash
bash scripts/worktree-env.sh prepare
```

Run in each worktree:

```bash
bash scripts/worktree-env.sh link-self
```

## 3. Assign tracks

Use `docs/workstreams/README.md` and Linear mapping in `docs/planning/linear-links.md`.

Recommended first split:

- Agent A: `RHE-12`, `RHE-13` (storage foundation)
- Agent B: `RHE-16`, `RHE-17` (telegram commands)
- Agent C: `RHE-14`, `RHE-15` (email ingest + orchestration)
- Agent D: `RHE-18`, `RHE-20` (digest + observability)

## 4. Daily sync

- Rebase each branch daily on `main`.
- Keep PRs narrow to one issue or one boundary.
- Require `scripts/lint.sh` + `scripts/test.sh` before push.
