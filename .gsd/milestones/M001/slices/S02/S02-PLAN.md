# S02: Specialist Dispatch And Approval Semantics

**Goal:** Implement kernel-owned specialist dispatch for `TaskAgent` and `CalendarAgent`, including durable invocation records and schedule proposal persistence.
**Demo:** Implement kernel-owned specialist dispatch for `TaskAgent` and `CalendarAgent`, including durable invocation records and schedule proposal persistence.

## Must-Haves


## Tasks

- [x] **T01: 02-specialist-dispatch-and-approval-semantics 01** `est:6 min`
  - Implement kernel-owned specialist dispatch for `TaskAgent` and `CalendarAgent`, including durable invocation records and schedule proposal persistence.

Purpose: Phase 2 starts by turning the Phase 1 workflow state machine into a typed specialist execution kernel that can drive the representative scheduling flow without yet introducing human approval or downstream writes.
Output: Specialist payload schemas, durable invocation persistence, typed dispatch registration, worker integration, and tests proving request-to-task-to-schedule progression.
- [x] **T02: 02-specialist-dispatch-and-approval-semantics 02** `est:9min`
  - Implement first-class approval checkpoints, operator decisions, and approval-driven resume semantics for schedule proposals.

Purpose: Phase 2 requires valid proposal artifacts to pause for human decision before any later side-effect phase can act on them. This plan turns approval into a durable kernel state with shared API and Telegram operator paths.
Output: Approval storage/contracts, checkpoint creation and decision handling, shared read-model updates, API routes, Telegram commands, and tests for approve/reject/revision resume behavior.
- [x] **T03: 02-specialist-dispatch-and-approval-semantics 03** `est:15min`
  - Implement revision-driven proposal versioning and operator-visible decision lineage for approval-driven rework.

Purpose: Phase 2 is incomplete if a revision request only edits the current proposal in place. This plan makes proposal rework durable and inspectable by version so approval history survives later retries, resumes, and downstream sync phases.
Output: Revision payload contracts, proposal-version lineage behavior, latest-first read-model updates, API and Telegram version inspection, runbook notes, and tests for supersession and version-specific decisions.

## Files Likely Touched

- `migrations/versions/20260313_0008_specialist_dispatch.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_steps.py`
- `packages/storage/src/helm_storage/repositories/__init__.py`
- `packages/orchestration/src/helm_orchestration/contracts.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/worker/src/helm_worker/jobs/registry.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_repositories.py`
- `migrations/versions/20260313_0009_approval_checkpoints.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_runs.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/routers/workflow_runs.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/unit/test_telegram_commands.py`
- `tests/integration/test_workflow_status_routes.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/api/src/helm_api/routers/workflow_runs.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py`
- `docs/runbooks/workflow-runs.md`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/unit/test_telegram_commands.py`
- `tests/integration/test_workflow_status_routes.py`
