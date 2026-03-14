# T03: 03-adapter-writes-and-recovery-guarantees 03

**Slice:** S03 — **Milestone:** M001

## Description

Add explicit replay lineage and terminate-safe recovery semantics inside the durable workflow kernel.

Purpose: Make recovery semantics explicit in storage and orchestration so retry, replay, termination, and partial sync success remain durable and unambiguous before any operator surface projects them.
Output: Recovery and replay lineage model updates, workflow-service semantics for same-run retry and terminate-after-partial-success, and tests proving history stays intact across those transitions.

## Must-Haves

- [ ] "Retry remains a same-run recovery action, while replay is recorded as an explicit re-execution event with preserved lineage to the prior execution."
- [ ] "Termination after partial sync success stops further outbound writes without deleting or rewriting already-succeeded sync lineage."
- [ ] "Recovery state stays queryable from durable storage and workflow events rather than being inferred from transient worker memory."

## Files

- `migrations/versions/20260313_0011_workflow_recovery_lineage.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/storage/src/helm_storage/repositories/replay_queue.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_repositories.py`
