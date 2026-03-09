# Contributing to Helm

## Scope Guardrails

- Follow `docs/internal/helm-v1.md` as source of truth.
- Prefer minimal, explicit implementations.
- Avoid scope expansion into multi-user/public SaaS concerns.

## Branch and PR

- One focused change per PR.
- Use PR title format: `feat|bug|chore: <short description>`.
- Link issue and include validation steps.

## Local Workflow

```bash
cp .env.example .env
make install
make lint
make test
```

## Required Checks Before PR

- `scripts/lint.sh`
- `scripts/test.sh`
- Manual verification notes when changing bot/api/worker behavior.

## Design Rules

- Persist workflow state in DB artifacts, not in process memory.
- Keep human approval for meaningful outbound actions.
- Keep LinkedIn integration optional unless explicitly enabled.

