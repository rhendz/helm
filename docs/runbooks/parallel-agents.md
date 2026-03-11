# Parallel Agents Runbook

## Goal

Let multiple Codex agents run in parallel with minimal environment/setup churn and low boundary collision risk.

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

This shared environment model is a Helm monorepo convenience. It should not be treated as the default for extracted `study-agent` or `email-agent` repos.

## 3. Assign tracks

Use `docs/workstreams/README.md` and select non-overlapping boundaries.

Preferred split:

- Helm host: `apps/api`, `apps/worker`, `apps/telegram-bot`, `packages/runtime`, `packages/observability`, `migrations`
- Email agent core: `packages/agents/src/email_agent`
- Study agent standalone: `apps/study-agent`
- Shared infra: CI, scripts, docs, repo-process changes

## 4. Daily sync

- Keep PRs narrow to one issue or one boundary.
- Run `scripts/lint.sh` + `scripts/test.sh` before push.
- Call out any contract change that affects extraction or repo boundaries.

## 5. Linear Usage

Use Linear selectively.

- Create a ticket when work needs handoff, sequencing, architectural memory, or follow-up beyond the current PR.
- Skip tickets for short-lived implementation steps inside one active boundary.
- Keep fast inner-loop development in PRs, docs, and focused TODOs.
