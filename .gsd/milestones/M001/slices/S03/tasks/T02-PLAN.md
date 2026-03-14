# T02: 03-adapter-writes-and-recovery-guarantees 02

**Slice:** S03 — **Milestone:** M001

## Description

Implement idempotent adapter execution, reconciliation-first recovery, and restart-safe resume for approved sync work.

Purpose: Make the Phase 03 sync manifest executable without duplicate side effects by ensuring the worker and orchestration layers always recover from durable sync records and only retry unresolved or failed items.
Output: Sync execution logic, durable outcome states, resume-service integration, worker wiring, and tests covering retry, restart, and duplicate-prevention behavior.

## Must-Haves

- [ ] "Retry and resume paths rebuild remaining adapter work from durable sync facts instead of in-memory progress."
- [ ] "Duplicate downstream writes are prevented across failure retry and post-restart resume by stable sync identity and idempotency data."
- [ ] "Uncertain write outcomes reconcile against persisted identity before Helm attempts another create, update, or delete."

## Files

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
