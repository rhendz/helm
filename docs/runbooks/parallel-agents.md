# Parallel Agents Runbook

## Goal

Let multiple Codex agents run in parallel with minimal environment/setup churn.

## 1. Create worktrees

```bash
git checkout main
git pull --ff-only

git worktree add ../helm-<track-a> -b ap/feat-<track-a> main
git worktree add ../helm-<track-b> -b ap/feat-<track-b> main
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

Use `docs/workstreams/README.md` and select any non-overlapping set of issues.

## 4. Daily sync

- Keep PRs narrow to one issue or one boundary.
- Run `scripts/lint.sh` + `scripts/test.sh` before push.
