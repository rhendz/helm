# T01: 03-adapter-writes-and-recovery-guarantees 01

**Slice:** S03 — **Milestone:** M001

## Description

Establish the durable sync-plan and adapter contract layer for approved workflow writes.

Purpose: Convert approval output into a persisted manifest of outbound task and calendar writes so later execution, retry, resume, and replay paths have stable sync identity and queryable lineage.
Output: Sync-record migration and ORM model, repository contracts, adapter protocols, orchestration support for deriving approved sync items, and tests proving approved proposals become durable write manifests.

## Must-Haves

- [ ] "Approved proposal items become durable sync records before any task-system or calendar-system side effect runs."
- [ ] "Task and calendar writes are initiated only through explicit adapter contracts owned by the orchestration boundary, never from workflow logic directly."
- [ ] "Every outbound write candidate is anchored to the exact approved proposal artifact and version so later retries and replays have a stable lineage key."

## Files

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
