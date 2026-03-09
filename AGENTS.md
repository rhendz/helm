# Helm Agent Collaboration Guide

This repository is intentionally organized for multiple Codex agents to work in parallel with low collision risk.

## Source Of Truth

- Product and scope source of truth: `docs/internal/helm-v1.md`.
- If implementation and spec conflict, align code to the spec and open a follow-up note when unclear.

## V1 Boundaries

- Single user, personal internal system.
- Telegram-first UX for V1.
- DB-first artifact model (Postgres as truth, not prompt memory).
- Human approval required for meaningful outbound actions.
- No frontend dashboard unless explicitly added by scope decision.
- LinkedIn integration remains optional/V1.x unless an explicit ingestion path is selected.

## Parallel Work Boundaries

Default split is one agent per boundary:

- `apps/api`: API routes, request/response schemas, admin/debug endpoints.
- `apps/worker`: schedules, workflow execution, retries.
- `apps/telegram-bot`: command handlers and approval interactions.
- `packages/storage`: SQLAlchemy models, repositories, migrations.
- `packages/connectors`: external system ingress.
- `packages/agents`: business logic per agent (email/linkedin/study/digest).
- `packages/orchestration`: LangGraph orchestration and workflow state transitions.
- `packages/llm`: model invocation and prompt contracts.
- `packages/observability`: logging, metrics, run traces.

## Engineering Conventions

- Keep modules boring and explicit. Avoid speculative abstractions.
- Add TODO markers with owner context where logic is intentionally deferred.
- Preserve strict boundaries: app layer orchestrates, package layer implements.
- Domain decisions should be represented as durable artifacts in storage.
- Use dependency injection where it improves testability, not everywhere by default.

## Workflow Conventions

- Branch naming: `ap/(feat|bug|chore)-short-description`.
- Do not include ticket IDs in branch names.
- If a Linear ticket exists, include it in PR description/body.
- PR title format: `feat|bug|chore: short description`.
- Create focused PRs scoped to one boundary.
- Run local checks before PR:
  - `scripts/lint.sh`
  - `scripts/test.sh`
- Update docs when contracts or workflows change.
- For API/worker/bot behavior changes, include manual verification notes.

## Safety

- Never commit secrets.
- Avoid logging full sensitive message bodies in default logs.
- Any potentially destructive operation must require explicit user action.

## Definition Of Done (Per Change)

- Feature aligns to V1 spec scope.
- Tests added/updated for changed behavior (or TODO with clear follow-up ticket).
- Relevant runbook/docs updated.
- No boundary leakage across package responsibilities.
