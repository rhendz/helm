# S01: Durable Workflow Foundation

**Goal:** Establish the durable Postgres persistence layer for workflow runs, step attempts, artifacts, and transition history.
**Demo:** Establish the durable Postgres persistence layer for workflow runs, step attempts, artifacts, and transition history.

## Must-Haves


## Tasks

- [x] **T01: 01-durable-workflow-foundation 01** `est:12 min`
  - Establish the durable Postgres persistence layer for workflow runs, step attempts, artifacts, and transition history.

Purpose: Create the kernel-owned workflow vocabulary and storage contracts that later orchestration and operator surfaces can rely on without reusing email-specific tables.
Output: Migration, ORM models, repository contracts, repository implementations, and repository tests for workflow foundation entities.
- [x] **T02: 01-durable-workflow-foundation 02** `est:6min`
  - Implement the typed orchestration and validation boundary that turns persisted workflow records into a durable, restart-safe workflow state machine.

Purpose: Phase 1 is not complete with storage alone; the kernel must own step advancement, validation failure blocking, and persisted failure/retryability semantics before later phases add approvals or side effects.
Output: Typed workflow schemas, validation services, orchestration services, worker polling/resume entrypoint, and service-level tests for success and blocked-state transitions.
- [x] **T03: 01-durable-workflow-foundation 03** `est:12min`
  - Expose durable workflow ingest and inspection through API and Telegram-friendly operator paths so users can start, inspect, and recover workflow runs without raw database access.

Purpose: The Phase 1 goal requires an explicit request-ingest path plus inspectable run status and lineage, not just persisted records. This plan turns the new kernel state into operator-facing API and Telegram flows for creation, triage, and recovery.
Output: Workflow run API schemas/routes/services, Telegram status service and commands, and route/read-model tests for start, status, lineage, and recovery visibility.

## Files Likely Touched

- `migrations/versions/20260313_0007_workflow_foundation.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_runs.py`
- `packages/storage/src/helm_storage/repositories/workflow_steps.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/storage/src/helm_storage/repositories/__init__.py`
- `tests/unit/test_workflow_repositories.py`
- `packages/orchestration/src/helm_orchestration/__init__.py`
- `packages/orchestration/src/helm_orchestration/contracts.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/validators.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/worker/src/helm_worker/jobs/registry.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `packages/orchestration/README.md`
- `tests/unit/test_workflow_orchestration_service.py`
- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/routers/workflow_runs.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/api/src/helm_api/main.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/telegram-bot/src/helm_telegram_bot/main.py`
- `docs/runbooks/workflow-runs.md`
- `tests/unit/test_workflow_status_service.py`
- `tests/integration/test_workflow_status_routes.py`
