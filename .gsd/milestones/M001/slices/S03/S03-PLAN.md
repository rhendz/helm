# S03: Adapter Writes And Recovery Guarantees

**Goal:** Establish the durable sync-plan and adapter contract layer for approved workflow writes.
**Demo:** Establish the durable sync-plan and adapter contract layer for approved workflow writes.

## Must-Haves


## Tasks

- [x] **T01: 03-adapter-writes-and-recovery-guarantees 01** `est:20 min`
  - Establish the durable sync-plan and adapter contract layer for approved workflow writes.

Purpose: Convert approval output into a persisted manifest of outbound task and calendar writes so later execution, retry, resume, and replay paths have stable sync identity and queryable lineage.
Output: Sync-record migration and ORM model, repository contracts, adapter protocols, orchestration support for deriving approved sync items, and tests proving approved proposals become durable write manifests.
- [x] **T02: 03-adapter-writes-and-recovery-guarantees 02** `est:17 min`
  - Implement idempotent adapter execution, reconciliation-first recovery, and restart-safe resume for approved sync work.

Purpose: Make the Phase 03 sync manifest executable without duplicate side effects by ensuring the worker and orchestration layers always recover from durable sync records and only retry unresolved or failed items.
Output: Sync execution logic, durable outcome states, resume-service integration, worker wiring, and tests covering retry, restart, and duplicate-prevention behavior.
- [x] **T03: 03-adapter-writes-and-recovery-guarantees 03** `est:10 min`
  - Add explicit replay lineage and terminate-safe recovery semantics inside the durable workflow kernel.

Purpose: Make recovery semantics explicit in storage and orchestration so retry, replay, termination, and partial sync success remain durable and unambiguous before any operator surface projects them.
Output: Recovery and replay lineage model updates, workflow-service semantics for same-run retry and terminate-after-partial-success, and tests proving history stays intact across those transitions.
- [x] **T04: 03-adapter-writes-and-recovery-guarantees 04** `est:9 min`
  - Expose Phase 03 recovery semantics through one shared workflow status projection.

Purpose: Make the durable sync and recovery facts from earlier Phase 03 plans legible to operators before execution and after partial success, while keeping the projection itself separate from API, worker, and Telegram entrypoint wiring.
Output: Shared workflow status projection updates and tests proving operators can inspect effect summaries, partial sync, and recovery state from one durable read model.
- [x] **T05: 03-adapter-writes-and-recovery-guarantees 05** `est:24min`
  - Wire operator-safe replay and recovery entrypoints on top of the shared Phase 03 status and kernel semantics.

Purpose: Make deliberate replay and recovery controls reachable through API, worker, and Telegram entrypoints without duplicating the durable recovery rules established earlier in the phase.
Output: API replay endpoints, replay service wiring, worker replay job integration, Telegram recovery commands, and tests proving operator-triggered replay is reachable end-to-end.

## Files Likely Touched

- `migrations/versions/20260313_0009_workflow_sync_records.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/storage/src/helm_storage/repositories/__init__.py`
- `packages/orchestration/src/helm_orchestration/contracts.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `tests/unit/test_workflow_repositories.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `migrations/versions/20260313_0010_workflow_sync_execution.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_runs.py`
- `packages/storage/src/helm_storage/repositories/workflow_steps.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/storage/src/helm_storage/repositories/__init__.py`
- `packages/connectors/src/helm_connectors/__init__.py`
- `packages/connectors/src/helm_connectors/task_system.py`
- `packages/connectors/src/helm_connectors/calendar_system.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_repositories.py`
- `migrations/versions/20260313_0011_workflow_recovery_lineage.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/storage/src/helm_storage/repositories/replay_queue.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_repositories.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `tests/unit/test_workflow_status_service.py`
- `apps/api/src/helm_api/main.py`
- `apps/api/src/helm_api/routers/replay.py`
- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/services/replay_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/main.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/worker/src/helm_worker/jobs/replay.py`
- `tests/unit/test_replay_service.py`
- `tests/unit/test_workflow_status_service.py`
