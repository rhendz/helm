# Contributing to Helm

## Scope Guardrails

- Follow `docs/internal/helm-v1.md` as source of truth.
- Prefer minimal, explicit implementations.
- Avoid scope expansion into multi-user/public SaaS concerns.
- Keep Helm focused on host concerns. Agent-specific domain logic should stay extractable.

## Modular Direction

- `apps/study-agent` is the canonical standalone study implementation.
- `packages/agents/src/email_agent` should remain host-agnostic. Helm-specific adapters belong in Helm host code, not in the agent core.
- Treat repo-level tooling as temporary monorepo glue where needed, not as a reason to couple study and email logic to Helm.

## Branch and PR

- One focused change per PR.
- Branch format:
  - `ap/feat-short-description`
  - `ap/bug-short-description`
  - `ap/chore-short-description`
- PR title format: `feat|bug|chore: short description`.
- If a Linear ticket exists, include it in PR description/body.
- Do not include ticket IDs in the branch name.
- Link issue and include validation steps.

## Local Workflow

```bash
bash scripts/bootstrap.sh
bash scripts/doctor.sh
bash scripts/verify.sh
```

For parallel Helm worktrees, use `bash scripts/worktree-env.sh link-self` after preparing the main repo once. Do not assume this shared `.venv` model should carry forward to extracted study/email repos.

## Required Checks Before PR

- `scripts/verify.sh`
- Manual verification notes when changing bot/api/worker behavior.
- CI is path-aware on PRs. Touching only docs or unrelated boundaries should not trigger the full Helm host validation stack.

## Linear Usage

- Use Linear for work that needs coordination, sequencing, or durable architectural memory.
- Preferred ticket types:
  - extraction and decoupling plans
  - CI/CD and repo-process changes
  - cross-boundary contract changes
  - deferred follow-ups that should survive beyond the current PR
- Avoid creating tickets for obvious short-lived inner-loop implementation steps.
- PRs, local docs, and targeted TODOs are the default tracking tools for rapid iteration inside a single boundary.

## Design Rules

- Persist workflow state in DB artifacts, not in process memory.
- Keep human approval for meaningful outbound actions.
