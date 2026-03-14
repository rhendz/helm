---
estimated_steps: 8
estimated_files: 2
---

# T02: Implement drift detection and reconciliation state update in orchestration service

**Slice:** S02 — External-Change Detection and Sync State Reconciliation
**Milestone:** M003

## Description

Extend `WorkflowOrchestrationService._reconcile_sync_record()` to handle the drift case: when the Calendar adapter returns `payload_fingerprint_matches=False`, indicating the operator manually edited the event. The orchestration service must:

1. Log drift detection clearly (grep-able "drift_detected" signal)
2. Extract field diffs from the live event details (title, start, end, description)
3. Create a durable workflow event with type `drift_detected_external_change` containing fingerprints and field diffs
4. Mark the sync record as DRIFT_DETECTED (using T01's new method)
5. Continue to the next sync record (don't fail the workflow, don't mark as succeeded)

This keeps reconciliation read-only (adapter doesn't write) while letting orchestration own the policy (marking drift as a durable state, not an error).

## Steps

1. Locate _sync_execution_step() method (line ~1090-1130) and the reconciliation check at line ~1106
2. In _sync_execution_step(), modify the reconciliation success check from `if reconciliation.found or reconciliation.payload_fingerprint_matches:` to split into two cases:
   - Case 1: `if reconciliation.found and reconciliation.payload_fingerprint_matches:` → mark_succeeded (existing behavior)
   - Case 2: `elif reconciliation.found and not reconciliation.payload_fingerprint_matches:` → handle drift (new)
3. For drift case: (a) log with structured data (stored_fingerprint, live_fingerprint, external_object_id, planned_item_key); (b) extract field diffs by comparing stored payload against reconciliation's live event details (title, start, end, description); (c) build event details dict; (d) create NewWorkflowEvent with event_type="drift_detected_external_change"; (e) call mark_drift_detected(); (f) continue to next record (don't return/fail/succeed)
4. Verify the else case still handles not-found scenarios (event disappeared, reconciliation failed)
5. Write integration tests: mock adapter returning SyncLookupResult with found=True and payload_fingerprint_matches=False, verify drift event created, sync marked DRIFT_DETECTED, logs emitted
6. Write additional test for happy path: found=True and payload_fingerprint_matches=True, verify no drift event created, sync marked SUCCEEDED
7. Verify existing reconciliation tests still pass (mark_succeeded path)
8. Lint and format (ruff, black, mypy)

## Must-Haves

- [ ] _reconcile_sync_record() checks payload_fingerprint_matches and handles False case
- [ ] Drift detection logs "drift_detected" signal with structured data (fingerprints, external_object_id)
- [ ] Field diffs extracted from live event details (title, start, end, description compared)
- [ ] Workflow event created with type "drift_detected_external_change" including fingerprints and field diffs in details
- [ ] Sync record marked DRIFT_DETECTED via mark_drift_detected() from T01
- [ ] Orchestration continues to next record after drift (does not fail step, does not mark as succeeded)
- [ ] Integration tests pass (mocked adapter with fingerprint mismatch)
- [ ] All existing tests pass (zero regressions)
- [ ] Ruff, mypy, black all pass

## Verification

- Run `pytest tests/integration/test_drift_detection_and_reconciliation.py::TestReconciliationStateUpdate -v` — passes
- Run `pytest tests/integration/test_drift_detection_and_reconciliation.py -v` — all drift detection tests pass
- Run `pytest tests/integration/test_weekly_scheduling_end_to_end.py -v` — all existing integration tests pass (zero regressions)
- Grep test logs for "drift_detected" signal in at least one test: `pytest ... -s | grep drift_detected` — present and structured
- Run `ruff check packages/orchestration/src/helm_orchestration/workflow_service.py` — no errors
- Run `mypy packages/orchestration/src/helm_orchestration/` — no type errors

## Observability Impact

- Signals added: `drift_detected` log emitted when fingerprints don't match; structured fields: stored_fingerprint, live_fingerprint, external_object_id, planned_item_key, field_diffs
- How a future agent inspects: grep logs for "drift_detected" string; query database `SELECT * FROM workflow_events WHERE event_type='drift_detected_external_change'` to see all recorded drifts with field diffs in details
- Failure state exposed: drift event is durable and observable; sync record status is DRIFT_DETECTED (queryable); no silent skipping

## Inputs

- `packages/orchestration/src/helm_orchestration/workflow_service.py` — _reconcile_sync_record() method and _sync_execution_step() caller (from M001)
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py` — mark_drift_detected() method from T01
- `packages/orchestration/src/helm_orchestration/schemas.py` — SyncLookupResult definition (already has payload_fingerprint_matches field)

## Expected Output

- _reconcile_sync_record() extended with drift case handling
- Orchestration creates drift events and marks sync records durably
- Integration tests pass proving drift detection flow
- Observability signals in place for diagnosing drift in production
