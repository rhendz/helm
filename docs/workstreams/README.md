# Parallel Workstreams

This file defines low-conflict tracks for parallel Codex agents.

Current modular direction:

- `apps/study-agent` is the canonical standalone study implementation.
- `packages/agents/src/email_agent` should stay extractable; Helm-specific adapters should live outside the agent core.
- Helm host work should stay focused on orchestration, transport, storage adapters, observability, and migrations.

## Track A: Storage + Migrations

- Directory focus: `packages/storage`, `migrations`, `docs/domain`.
- Deliverables:
  - Full SQLAlchemy models for V1 entities.
  - Alembic baseline migration.
  - Repository interfaces + tests.

## Track B: API

- Directory focus: `apps/api`, `docs/contracts`.
- Deliverables:
  - Internal trigger/admin endpoints.
  - Request/response schemas.
  - Health/status endpoints with DB/worker checks.

## Track C: Worker + Orchestration

- Directory focus: `apps/worker`, `packages/orchestration`, `packages/agents`.
- Deliverables:
  - Job registry and scheduler.
  - Helm-side workflow wiring and retry/error handling.
  - Runtime composition that does not leak Helm concerns into extractable agent cores.

## Track D: Telegram Bot

- Directory focus: `apps/telegram-bot`.
- Deliverables:
  - Command handlers (`/digest`, `/drafts`, `/actions`).
  - Approval/snooze command contracts.

## Track E: Connectors + LLM

- Directory focus: `packages/connectors`, `packages/llm`.
- Deliverables:
  - Gmail ingest path.
  - LLM prompt contract helpers.

## Track F: Agent Extraction

- Directory focus: `apps/study-agent`, `packages/agents/src/email_agent`, CI/docs/process files.
- Deliverables:
  - Clear host-vs-agent ownership boundaries.
  - Removal of Helm-specific adapter placement from agent-core packages.
  - Repo/process changes that support future extraction into standalone repos.



## Intake

- Refresh inbox from Linear with `uv run --frozen --extra dev python scripts/linear_intake.py export-md --output docs/workstreams/linear-inbox.md`.
- Use `docs/workstreams/linear-inbox.md` as a current read-only queue snapshot.
