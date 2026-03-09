# Parallel Workstreams

This file defines low-conflict tracks for parallel Codex agents.

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
  - Email triage workflow skeleton.
  - Retry/error handling scaffolding.

## Track D: Telegram Bot

- Directory focus: `apps/telegram-bot`.
- Deliverables:
  - Command handlers (`/digest`, `/drafts`, `/actions`, `/study`).
  - Approval/snooze command contracts.

## Track E: Connectors + LLM

- Directory focus: `packages/connectors`, `packages/llm`.
- Deliverables:
  - Gmail ingest path.
  - LLM prompt contract helpers.
  - Optional LinkedIn manual connector scaffolding.

