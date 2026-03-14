# S01: Durable Workflow Foundation

**Established the durable Postgres persistence layer for workflow runs, step attempts, artifacts, transition history, and shared operator surfaces.**

## What Happened

S01 built the kernel's persistence foundation in three tasks. T01 added dedicated `workflow_runs`, `workflow_steps`, `workflow_artifacts`, and `workflow_events` tables with typed SQLAlchemy models and repository contracts. T02 layered typed orchestration schemas (requests, artifacts, validation reports, execution failures, final summaries) and durable workflow state machine services for validation gating, retry, terminate, and resume. T03 exposed durable workflow state through a shared read-model service consumed by both FastAPI API routes and Telegram bot commands for workflow creation, inspection, triage, and recovery.

## Key Outcomes

- Workflow-native Postgres tables with foreign-key relationships and versioned artifact lineage.
- Typed Pydantic schemas for all workflow payloads with a validator registry.
- Orchestration services owning step advancement, validation-failure blocking, and restart-safe resume.
- Shared workflow status projection with explicit `paused_state` and `available_actions`.
- API endpoints for create, list, detail, retry, and terminate.
- Telegram commands for start, summary, needs-action review, and recovery.

## Verification

- `test_workflow_repositories.py`: schema creation, lineage, blocked validation, execution failure, resume-safe reads.
- `test_workflow_orchestration_service.py`: validation, blocked-run, failure, retry, terminate, resume, and final-summary coverage.
- `test_workflow_status_service.py`: read-model coverage for blocked, failed, completed, and lineage cases.
- `test_workflow_status_routes.py`: API coverage for all workflow routes.
- `test_telegram_commands.py`: Telegram workflow command coverage.

## Tasks

- T01 (12 min): Durable workflow foundation schema, ORM models, and repository contracts.
- T02 (6 min): Typed orchestration schemas, validation services, and worker resume entrypoint.
- T03 (12 min): Shared workflow status read model, API routes, and Telegram commands.
