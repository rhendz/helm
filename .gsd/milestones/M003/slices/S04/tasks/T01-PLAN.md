# T01: Recovery Classification and Safe Actions Mapping

**Assign recovery_classification to drift-detected records; map DRIFT_DETECTED to safe_next_actions in status service. Drift-detected workflows can be safely recovered via operator-initiated replay.**

## Purpose

S02 created DRIFT_DETECTED sync records, but they have no recovery classification. Status service's _safe_next_actions() doesn't know what actions to expose for drifted records. This task bridges the gap: assign classifications and map them to safe actions, so Telegram can show recovery options to the operator.

## Must-Haves

- [ ] Drifted sync records have recovery_classification assigned (not null)
- [ ] recovery_classification = TERMINAL_FAILURE (passive policy: requires operator to initiate recovery)
- [ ] _safe_next_actions() in workflow_status_service.py returns [request_replay] for TERMINAL_FAILURE records
- [ ] No auto-retry or terminate actions exposed for drifted records (prevent fighting operator edits)
- [ ] Unit tests: classification assignment logic, action mapping consistency
- [ ] Integration tests: status service projection with drifted records produces correct safe_next_actions
- [ ] Zero regressions (full suite passes)

## Inputs

- `packages/orchestration/src/helm_orchestration/workflow_service.py` — current _handle_drift_detected() method (no classification assigned yet)
- `packages/storage/src/helm_storage/repositories/contracts.py` — RecoveryClassification enum (RECOVERABLE_FAILURE, TERMINAL_FAILURE, etc.)
- `apps/api/src/helm_api/services/workflow_status_service.py` — _safe_next_actions() method (already handles some classifications)
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py` — mark_drift_detected() method signature
- Existing M001 tests for reference patterns

## Expected Output

- Modified `workflow_service.py`: _handle_drift_detected() assigns recovery_classification = TERMINAL_FAILURE to drifted records
- Modified `workflow_status_service.py`: _safe_next_actions() maps DRIFT_DETECTED/TERMINAL_FAILURE to [request_replay]
- New `tests/unit/test_recovery_classification_for_drift.py` with 5 unit tests
- New `tests/integration/test_drift_recovery_actions_in_workflow_status.py` with 2 integration tests
- All tests pass; zero regressions

## Steps

### 1. Understand existing recovery classification patterns
- Read `packages/storage/src/helm_storage/repositories/contracts.py`, RecoveryClassification enum
  - Note: RECOVERABLE_FAILURE, TERMINAL_FAILURE, RETRY_REQUESTED, REPLAY_REQUESTED, TERMINATED_AFTER_PARTIAL_SUCCESS
  - DRIFT_DETECTED status exists but no classification assigned
- Read `packages/storage/src/helm_storage/repositories/workflow_sync_records.py`, mark_failed() method
  - Note: how classification is assigned, what fields are updated
- Read `apps/api/src/helm_api/services/workflow_status_service.py`, _safe_next_actions() method
  - Note: current mappings (RECOVERABLE_FAILURE → [retry, terminate], TERMINAL_FAILURE → [request_replay], etc.)
  - Note: no case for DRIFT_DETECTED yet

### 2. Analyze decision: which recovery_classification for drift?
- Options:
  - A: TERMINAL_FAILURE (requires operator replay, prevents auto-retry)
  - B: RECOVERABLE_FAILURE (eligible for auto-retry, but risky if operator still editing)
  - C: New enum DRIFT_REQUIRES_DECISION (explicit, but requires schema changes)
- Decision: Use **TERMINAL_FAILURE** (passive policy chosen in T02)
  - Drift represents operator intent; auto-retry risks fighting the edit
  - request_replay respects original Helm intent and allows recovery
  - Matches R011 requirement (operator intent is ground truth)
  - No schema changes needed
  - Recovery action: [request_replay] only (no auto-retry)

### 3. Modify _handle_drift_detected() in workflow_service.py
- Locate: `packages/orchestration/src/helm_orchestration/workflow_service.py`, method `_handle_drift_detected()`
- Current behavior: extract diffs, log, create event, call mark_drift_detected()
- Add: after mark_drift_detected() returns sync_record, assign recovery_classification
  ```python
  sync_record = self.sync_records_repo.mark_drift_detected(...)
  sync_record.recovery_classification = RecoveryClassification.TERMINAL_FAILURE
  self.sync_records_repo.save(sync_record)  # or update immediately if mark_drift_detected doesn't return record
  ```
- Alternative: pass recovery_classification as parameter to mark_drift_detected() if method signature allows
- Action: update mark_drift_detected() call site or post-update sync_record.recovery_classification
- Verify: log "recovery_classification_assigned_to_drift" with sync_record_id, classification for observability

### 4. Map DRIFT_DETECTED to safe_next_actions in workflow_status_service.py
- Locate: `apps/api/src/helm_api/services/workflow_status_service.py`, method `_safe_next_actions(sync_record)`
- Current structure: switch on recovery_classification, return action list
- Add case for TERMINAL_FAILURE from drifted records:
  ```python
  if recovery_classification == RecoveryClassification.TERMINAL_FAILURE:
    return ["request_replay"]  # or include proposed action name if active policy
  ```
- Verify: drifted records don't match any other cases (no auto-retry, no terminate)
- Verify: non-drifted TERMINAL_FAILURE records still get their actions (check for false positives)

### 5. Write unit tests: recovery classification logic
- File: `tests/unit/test_recovery_classification_for_drift.py` (new)
- Test 1: test_classification_assigned_on_drift_detected
  - Setup: mock sync_record, mock mark_drift_detected to return record
  - Call: _handle_drift_detected()
  - Assert: sync_record.recovery_classification == TERMINAL_FAILURE
  - Assert: log contains "recovery_classification_assigned_to_drift"
- Test 2: test_classification_is_terminal_not_recoverable
  - Setup: drifted sync_record with TERMINAL_FAILURE classification
  - Assert: classification != RECOVERABLE_FAILURE (prevent auto-retry)
- Test 3: test_classification_persisted_to_database
  - Setup: sync_record with recovery_classification set
  - Execute: save to repository
  - Assert: retrieve from repository, classification is persisted
- Test 4: test_classification_null_on_pending_record
  - Setup: sync_record in PENDING status
  - Assert: recovery_classification is null (classification only set on completion)
- Test 5: test_classification_differs_from_regular_failure
  - Setup: two sync records, one drifted (TERMINAL_FAILURE), one failed (FAILED_RETRYABLE)
  - Assert: classifications differ, different recovery actions apply

### 6. Write unit tests: safe_next_actions mapping
- File: same as above or split if > 10 assertions
- Test 6: test_drift_detected_maps_to_request_replay
  - Setup: sync_record with status=DRIFT_DETECTED, recovery_classification=TERMINAL_FAILURE
  - Call: _safe_next_actions(sync_record)
  - Assert: ["request_replay"] in result
  - Assert: "retry" and "terminate" NOT in result
- Test 7: test_multiple_drifted_records_same_actions
  - Setup: 3 sync records, all drifted with TERMINAL_FAILURE
  - Call: _safe_next_actions() on each
  - Assert: all return ["request_replay"] (consistent)
- Test 8: test_non_drifted_terminal_failure_unchanged
  - Setup: sync_record with status=FAILED_TERMINAL (not DRIFT_DETECTED), recovery_classification=TERMINAL_FAILURE
  - Call: _safe_next_actions(sync_record)
  - Assert: actions unchanged from existing behavior (e.g., ["request_replay"])

### 7. Write integration tests: workflow status projection with drifted records
- File: `tests/integration/test_drift_recovery_actions_in_workflow_status.py` (new)
- Test 9: test_drift_record_recovery_actions_in_status_projection
  - Setup: create workflow run, create sync_record in DRIFT_DETECTED status with diffs
  - Execute: query status projection via workflow_status_service
  - Assert: safe_next_actions includes "request_replay"
  - Assert: assert formatted Telegram output would show recovery option
- Test 10: test_multiple_records_mixed_status
  - Setup: 3 sync records: A=SUCCEEDED, B=DRIFT_DETECTED, C=FAILED_TERMINAL
  - Execute: compute safe_next_actions for entire run
  - Assert: A has no recovery actions; B has [request_replay] from drift; C has [request_replay] from failure
  - Assert: status projection aggregates correctly (e.g., "needs_action=true" because B or C drifted/failed)

### 8. Run tests and verify zero regressions
- Execute: `scripts/test.sh`
- Expected: All new tests pass (8 unit + 2 integration + existing suite)
- Execute: `ruff check .`, `mypy packages/`, `black --check .`
- Expected: No linting violations

## Verification Checklist

- [ ] _handle_drift_detected() assigns recovery_classification = TERMINAL_FAILURE to drifted records
- [ ] Drift records have recovery_classification persisted to database (not null)
- [ ] _safe_next_actions() maps TERMINAL_FAILURE to ["request_replay"]
- [ ] Drifted records don't expose auto-retry or terminate actions
- [ ] All 8 unit tests pass (classification assignment, mapping, edge cases)
- [ ] All 2 integration tests pass (status projection with drifted records)
- [ ] Full test suite passes (zero regressions)
- [ ] Linting passes (ruff, mypy, black)
- [ ] Observability logs present: "recovery_classification_assigned_to_drift" signal
- [ ] Code patterns match existing M001 conventions (mark_failed, _safe_next_actions)

## Observability Impact

- New structured log "recovery_classification_assigned_to_drift" emitted when drift is processed
  - Fields: sync_record_id, recovery_classification, sync_record.planned_item_key
  - Enables verification that all drifted records are properly classified
- Existing "safe_next_actions_computed" log now includes drift records with correct actions
- Database: workflow_sync_records.recovery_classification is non-null for all completed syncs (drift or failure)

## Done When

- T01 complete: All 10 test cases pass; recovery_classification assigned and mapped; zero regressions; observability logs captured.

