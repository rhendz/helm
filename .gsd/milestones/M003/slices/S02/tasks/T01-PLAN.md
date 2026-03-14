---
estimated_steps: 6
estimated_files: 3
---

# T01: Extend sync record state machine with DRIFT_DETECTED status and drift marking method

**Slice:** S02 — External-Change Detection and Sync State Reconciliation
**Milestone:** M003

## Description

Add DRIFT_DETECTED status to the `WorkflowSyncStatus` enum and implement a `mark_drift_detected()` repository method that updates sync records when drift is detected. This establishes the durable state transition path so orchestration can mark records as drifted without inventing new error states or conflating drift with failure.

The mark_drift_detected() method follows the existing pattern (mark_succeeded, mark_failed) and uses WorkflowSyncRecordPatch for clean, type-safe updates.

## Steps

1. Add DRIFT_DETECTED to WorkflowSyncStatus enum in contracts.py (after UNCERTAIN_NEEDS_RECONCILIATION, before CANCELLED)
2. Verify the enum is correctly imported in workflow_service.py and all affected modules
3. Add mark_drift_detected(sync_record_id: int, live_fingerprint: str, field_diffs: dict[str, Any]) method to SQLAlchemyWorkflowSyncRecordRepository, following the existing mark_failed() pattern
4. The method should: call update() with WorkflowSyncRecordPatch setting status=DRIFT_DETECTED, completed_at=_now(), and store live_fingerprint + field_diffs in last_error_summary (as JSON) or a new dedicated field if needed
5. Write unit tests: happy path (sync record exists, marked successfully), sync record not found (returns None), exception on session commit (raises)
6. Lint and format all changes (ruff, black, mypy)

## Must-Haves

- [ ] DRIFT_DETECTED added to WorkflowSyncStatus enum with appropriate docstring comment
- [ ] mark_drift_detected() method implemented following mark_failed() pattern
- [ ] Method signature clear: sync_record_id, live_fingerprint, field_diffs as parameters
- [ ] Unit tests cover happy path, not-found case, and exception handling (3+ tests)
- [ ] All tests pass (both new unit tests and all existing tests)
- [ ] Ruff, mypy, black all pass on modified files

## Verification

- Run `pytest tests/unit/test_workflow_sync_records.py::TestMarkDriftDetected -v` — all 3+ tests pass
- Run `pytest tests/unit/test_workflow_sync_records.py -v` — all existing tests still pass (zero regressions)
- Run `ruff check packages/storage/src/helm_storage/repositories/contracts.py packages/storage/src/helm_storage/repositories/workflow_sync_records.py` — no errors
- Run `mypy packages/storage/src/helm_storage/repositories/` — no type errors for modified files
- Run `black --check packages/storage/src/helm_storage/repositories/` — formatting clean

## Inputs

- `packages/storage/src/helm_storage/repositories/contracts.py` — current WorkflowSyncStatus enum and WorkflowSyncRecordPatch class (from M001)
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py` — existing mark_succeeded(), mark_failed() methods (from M001) as reference patterns

## Expected Output

- WorkflowSyncStatus.DRIFT_DETECTED added to enum
- SQLAlchemyWorkflowSyncRecordRepository.mark_drift_detected() method, fully implemented and tested
- 3+ passing unit tests in tests/unit/test_workflow_sync_records.py
- Zero regressions in existing tests

## Observability Impact

**New signals:**
- `mark_drift_detected()` operation is fully instrumented: method entry/exit logs with sync_record_id, live_fingerprint, and field_diffs passed as structured kwargs
- Database state change: `workflow_sync_records` row transitions to `status='DRIFT_DETECTED'` with `completed_at` set and drift metadata stored in `last_error_summary` (JSON)

**Future inspection:**
- Query: `SELECT id, status, last_error_summary FROM workflow_sync_records WHERE status='DRIFT_DETECTED'` — shows all detected drifts with metadata
- Grep logs for `mark_drift_detected` with sync_record_id to trace the operation
- Unit tests explicitly verify the state transition (happy path, not-found, exception handling)

**Failure visibility:**
- If `mark_drift_detected()` encounters a sync record not found, it returns `None` (no exception) — logs will show the miss
- If session commit fails, exception is raised with full context (sync_record_id, operation type)
- Test coverage ensures these paths are observable and recoverable

**Redaction constraints:** None — fingerprints and diffs are debug-only data, not PII
