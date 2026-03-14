# T03: Integration Tests and Operator-Safe Recovery Proof

**Prove drift-to-recovery workflows execute safely without silent corruption. Write comprehensive integration tests covering drift → retry/replay and partial failure scenarios. Create UAT script operator can follow to verify drift detection and recovery in their own environment.**

## Purpose

S04 must prove that drift-detected workflows can be safely recovered. T01 assigned classifications; T02 locked in passive policy. T03 validates all recovery paths work end-to-end: drift detection, recovery action exposure, replay initiation, state reconciliation. Integration tests prove no silent corruption; UAT script enables operator verification.

## Must-Haves

- [ ] 5 integration test scenarios pass: drift→replay, partial failure→terminate, mixed outcomes, replay after drift, edge cases
- [ ] All tests verify drift detection, recovery classification, safe_next_actions, Telegram UX, state transitions
- [ ] UAT script (S04-UAT.md) is operator-readable with clear steps, prerequisite check, verification queries
- [ ] UAT script covers: auth setup, event creation, manual edit, drift detection, recovery action, reconciliation
- [ ] No silent corruption paths: all test scenarios verify complete audit trail and state consistency
- [ ] Zero regressions (full suite passes)

## Inputs

- T01 outputs: recovery classification logic, safe_next_actions mapping (used in test assertions)
- T02 outputs: passive reconciliation policy decision (shapes test design and recovery action expectations)
- S02 implementation: drift detection, DRIFT_DETECTED status, drift_detected_external_change events
- Existing M001 integration test patterns (e.g., test_weekly_scheduling_end_to_end.py)
- Existing repository and orchestration APIs for drift record queries

## Expected Output

- New `tests/integration/test_drift_recovery_workflows.py` with 5 comprehensive scenarios
- New `.gsd/milestones/M003/slices/S04/S04-UAT.md` operator-runnable UAT script
- All tests pass; zero regressions
- Observability verified: structured logs for all state transitions

## Steps

### 1. Review existing integration test patterns
- Read `tests/integration/test_weekly_scheduling_end_to_end.py` (from M001)
  - Pattern: setup workflow run, create approvals, execute sync, assert outcomes
  - Note: mocking strategies for adapter calls, database queries for state verification
- Read `tests/integration/test_drift_detection_and_reconciliation.py` (from S02)
  - Pattern: setup sync record in UNCERTAIN_NEEDS_RECONCILIATION, mock adapter with drift response, trigger reconciliation
  - Note: assertion patterns for drift event creation, status transitions, field diffs
- Note: review conftest.py for test fixtures (workflow repos, adapters, mocks)

### 2. Plan integration test scenarios
- **Scenario A: Drift → Request Replay**
  - Setup: sync record in UNCERTAIN_NEEDS_RECONCILIATION with stored payload
  - Mock adapter: reconcile_calendar_block returns drift (payload_fingerprint_matches=False)
  - Execute: sync reconciliation step
  - Assert: record marked DRIFT_DETECTED, recovery_classification = TERMINAL_FAILURE, drift event created, field diffs extracted
  - Assert: safe_next_actions includes [request_replay]
  - Assert: operator can call request_replay() to initiate recovery
  - Result: drift detection → recovery action available to operator

- **Scenario B: Partial Failure → Terminate**
  - Setup: 3 sync records in PENDING (A, B, C)
  - Mock adapter: A succeeds, B fails with 500 error (retriable), C pending
  - Execute: sync step with termination on first failure
  - Assert: A=SUCCEEDED, B=FAILED_TERMINAL, C=CANCELLED, termination_summary with correct counts
  - Assert: safe_next_actions for run includes [request_replay] (operator can recover)
  - Assert: database shows partial counts: total_writes=1, calendar_writes=1 succeeded, 1 failed
  - Result: partial failure is visible, recovery actions available

- **Scenario C: Mixed Outcomes (Success, Drift, Not Attempted)**
  - Setup: 3 sync records (A calendar, B calendar, C task)
  - Mock adapter: A succeeds, B drifts, C pending (not executed due to lack of task adapter)
  - Execute: full sync step without termination
  - Assert: A=SUCCEEDED, B=DRIFT_DETECTED, C=PENDING
  - Assert: safe_next_actions for run shows mixed state: A can be ignored, B requires replay, C can be executed
  - Assert: workflow completes with mixed outcomes (not failed, not succeeded, requires operator attention)
  - Result: workflow transparency with partial completion and targeted recovery

- **Scenario D: Replay After Drift**
  - Setup: initial sync results in drift (record marked DRIFT_DETECTED, recovery_classification=TERMINAL_FAILURE)
  - Execute: operator calls request_replay() to initiate recovery
  - Assert: new sync lineage created from approved proposal
  - Mock adapter: reconcile_calendar_block now returns no drift (operator didn't edit further, or edit matched Helm intent)
  - Execute: reconciliation step on new lineage
  - Assert: new lineage record marked SUCCEEDED
  - Assert: old lineage preserved with drift history (audit trail)
  - Assert: workflow completes with new lineage success
  - Result: drift recovery via replay works end-to-end

- **Scenario E: Multiple Syncs, Some Drifted**
  - Setup: 4 sync records in UNCERTAIN_NEEDS_RECONCILIATION (2 calendar, 2 task) — would be executed in order
  - Mock adapter: 1st calendar succeeds, 2nd calendar drifts, tasks both pending
  - Execute: sync step (no termination on first failure)
  - Assert: 1st=SUCCEEDED, 2nd=DRIFT_DETECTED, 3rd/4th=PENDING
  - Assert: status projection shows: 1 succeeded + 1 drifted + 2 pending
  - Assert: safe_next_actions aggregates: [request_replay] because drift exists
  - Result: complex multi-sync scenarios are handled correctly

### 3. Write test_drift_request_replay (Scenario A)
- File: `tests/integration/test_drift_recovery_workflows.py` (new)
- Test function: test_drift_detected_triggers_recovery_action
  ```python
  def test_drift_detected_triggers_recovery_action(db_session, workflow_factory, adapter_mocks):
      # Setup
      run = workflow_factory.create_run_with_pending_sync(status="UNCERTAIN_NEEDS_RECONCILIATION")
      sync_record = run.sync_records[0]
      stored_payload = {"title": "Meeting", "start": "2026-03-14T14:00:00Z", "end": "2026-03-14T15:00:00Z"}
      sync_record.payload = stored_payload
      db_session.commit()
      
      # Mock adapter returns drift
      live_event = {..."start": "2026-03-14T15:00:00Z", "end": "2026-03-14T16:00:00Z"}  # manually rescheduled
      adapter_mocks.reconcile_result = SyncLookupResult(
          found=True,
          payload_fingerprint_matches=False,
          live_event=live_event
      )
      
      # Execute reconciliation
      orchestration_service = WorkflowOrchestrationService(db_session, adapter_mocks)
      orchestration_service._sync_execution_step(run)
      
      # Assert: drift detected and recorded
      db_session.refresh(sync_record)
      assert sync_record.status == WorkflowSyncStatus.DRIFT_DETECTED
      assert sync_record.recovery_classification == RecoveryClassification.TERMINAL_FAILURE
      
      # Assert: drift event created
      drift_events = [e for e in run.workflow_events if e.event_type == "drift_detected_external_change"]
      assert len(drift_events) == 1
      assert "field_diffs" in drift_events[0].details
      
      # Assert: safe_next_actions includes request_replay
      status_service = WorkflowStatusService(db_session)
      status = status_service.get_run_status(run.id)
      assert "request_replay" in status.safe_next_actions
      assert "retry" not in status.safe_next_actions  # passive policy: no auto-retry
  ```

### 4. Write test_partial_failure_termination (Scenario B)
- Test function: test_partial_failure_termination_preserves_state
  ```python
  def test_partial_failure_termination_preserves_state(db_session, workflow_factory, adapter_mocks):
      # Setup: 3 syncs (A succeeds, B fails, C pending)
      run = workflow_factory.create_run_with_sync_records([
          {"target": "calendar", "kind": "create", "status": "PENDING"},  # A
          {"target": "calendar", "kind": "create", "status": "PENDING"},  # B
          {"target": "task", "kind": "create", "status": "PENDING"}       # C
      ])
      
      # Mock: A succeeds, B fails, C not executed
      adapter_mocks.upsert_responses = [
          CalendarSyncResult(status="success", external_object_id="event_1", ...),  # A
          CalendarSyncResult(status="failed", retry_disposition="TERMINAL", ...),   # B (500 error)
          None  # C not executed
      ]
      
      # Execute sync step with termination
      orchestration_service = WorkflowOrchestrationService(db_session, adapter_mocks)
      orchestration_service._sync_execution_step(run)
      run.terminate()  # terminate on failure
      
      # Assert: partial state preserved
      db_session.refresh(run)
      syncs_by_status = {s.status: s for s in run.sync_records}
      assert syncs_by_status[WorkflowSyncStatus.SUCCEEDED].count == 1  # A
      assert syncs_by_status[WorkflowSyncStatus.FAILED_TERMINAL].count == 1  # B
      assert syncs_by_status[WorkflowSyncStatus.CANCELLED].count == 1  # C
      
      # Assert: termination summary records counts
      termination_event = [e for e in run.workflow_events if e.event_type == "terminated"]
      assert termination_event[0].details["total_writes"] == 2
      assert termination_event[0].details["calendar_writes"] == 2
      assert termination_event[0].details["succeeded_count"] == 1
      
      # Assert: safe_next_actions includes request_replay for recovery
      status_service = WorkflowStatusService(db_session)
      status = status_service.get_run_status(run.id)
      assert "request_replay" in status.safe_next_actions
      assert status.recovery_classification == "TERMINATED_AFTER_PARTIAL_SUCCESS"
  ```

### 5. Write test_mixed_outcomes (Scenario C)
- Test function: test_mixed_outcomes_success_drift_pending
  ```python
  def test_mixed_outcomes_success_drift_pending(db_session, workflow_factory, adapter_mocks):
      # Setup: 3 syncs (A succeeds, B drifts, C pending)
      run = workflow_factory.create_run_with_sync_records([
          {"target": "calendar", ...},  # A
          {"target": "calendar", ...},  # B
          {"target": "task", ...}       # C
      ])
      
      # Mock: A succeeds, B drifts, C pending
      adapter_mocks.upsert_responses = [
          CalendarSyncResult(...success...),  # A
          None  # B will be checked during reconciliation (drift)
      ]
      adapter_mocks.reconcile_responses = [
          SyncLookupResult(found=True, payload_fingerprint_matches=True, ...),  # A already succeeded
          SyncLookupResult(found=True, payload_fingerprint_matches=False, ...),  # B drifted
      ]
      
      # Execute
      orchestration_service = WorkflowOrchestrationService(db_session, adapter_mocks)
      orchestration_service._sync_execution_step(run)
      
      # Assert: mixed outcomes
      db_session.refresh(run)
      statuses = [s.status for s in run.sync_records]
      assert WorkflowSyncStatus.SUCCEEDED in statuses  # A
      assert WorkflowSyncStatus.DRIFT_DETECTED in statuses  # B
      assert WorkflowSyncStatus.PENDING in statuses  # C
      
      # Assert: workflow doesn't fail, shows needs_action
      assert run.status != "failed"
      status_service = WorkflowStatusService(db_session)
      status = status_service.get_run_status(run.id)
      assert status.needs_action == True  # operator must decide on drift
      assert "request_replay" in status.safe_next_actions
  ```

### 6. Write test_replay_after_drift (Scenario D)
- Test function: test_replay_after_drift_creates_new_lineage
  ```python
  def test_replay_after_drift_creates_new_lineage(db_session, workflow_factory, adapter_mocks, orchestration_service):
      # Setup: initial run with drift
      run = workflow_factory.create_run_with_sync_drift()  # A succeeds, B drifts
      
      # Execute: request replay on drifted record
      drifted_record = [s for s in run.sync_records if s.status == WorkflowSyncStatus.DRIFT_DETECTED][0]
      replay_response = orchestration_service.request_replay(run.id, drifted_record.id)
      assert replay_response.success == True
      
      # Assert: new sync lineage created
      db_session.refresh(run)
      new_generation = max(s.lineage_generation for s in run.sync_records)
      new_records = [s for s in run.sync_records if s.lineage_generation == new_generation]
      assert len(new_records) > 0
      assert new_records[0].status == WorkflowSyncStatus.PENDING  # ready to execute
      
      # Mock: reconcile now returns no drift
      adapter_mocks.reconcile_responses = [
          SyncLookupResult(found=True, payload_fingerprint_matches=True, ...)  # no drift
      ]
      
      # Execute: reconciliation on new lineage
      orchestration_service._sync_execution_step(run)
      
      # Assert: new lineage succeeds
      db_session.refresh(run)
      new_records = [s for s in run.sync_records if s.lineage_generation == new_generation]
      assert new_records[0].status == WorkflowSyncStatus.SUCCEEDED
      
      # Assert: old lineage preserved (audit trail)
      old_records = [s for s in run.sync_records if s.lineage_generation < new_generation]
      assert any(s.status == WorkflowSyncStatus.DRIFT_DETECTED for s in old_records)
      
      # Assert: workflow completes successfully
      assert run.status == "completed"
  ```

### 7. Write test_multiple_drifted_records (Scenario E)
- Test function: test_multiple_syncs_some_drifted
  ```python
  def test_multiple_syncs_some_drifted(db_session, workflow_factory, adapter_mocks):
      # Setup: 4 syncs (2 calendar, 2 task)
      run = workflow_factory.create_run_with_sync_records([
          {"target": "calendar", ...},  # A
          {"target": "calendar", ...},  # B
          {"target": "task", ...},      # C
          {"target": "task", ...}       # D
      ])
      
      # Mock: A succeeds, B drifts, C/D pending
      adapter_mocks.upsert_responses = [
          CalendarSyncResult(...success...),
          None  # B will reconcile
      ]
      adapter_mocks.reconcile_responses = [
          SyncLookupResult(found=True, payload_fingerprint_matches=True, ...),  # A
          SyncLookupResult(found=True, payload_fingerprint_matches=False, ...)   # B drifted
      ]
      
      # Execute
      orchestration_service = WorkflowOrchestrationService(db_session, adapter_mocks)
      orchestration_service._sync_execution_step(run)
      
      # Assert: aggregated state
      db_session.refresh(run)
      succeeded = [s for s in run.sync_records if s.status == WorkflowSyncStatus.SUCCEEDED]
      drifted = [s for s in run.sync_records if s.status == WorkflowSyncStatus.DRIFT_DETECTED]
      pending = [s for s in run.sync_records if s.status == WorkflowSyncStatus.PENDING]
      assert len(succeeded) == 1
      assert len(drifted) == 1
      assert len(pending) == 2
      
      # Assert: status projection aggregates correctly
      status_service = WorkflowStatusService(db_session)
      status = status_service.get_run_status(run.id)
      assert status.sync_summary["succeeded"] == 1
      assert status.sync_summary["drifted"] == 1
      assert status.sync_summary["pending"] == 2
      assert "request_replay" in status.safe_next_actions  # because of drift
  ```

### 8. Write UAT script (S04-UAT.md)
- File: `.gsd/milestones/M003/slices/S04/S04-UAT.md` (new)
- Content structure:
  ```markdown
  # S04 UAT: Drift Detection and Recovery in Your Calendar
  
  **Operator-runnable verification that drift detection, recovery actions, and safe reconciliation work in a real environment.**
  
  ## Prerequisites
  - [ ] Helm running locally (`scripts/dev.sh` started)
  - [ ] Google Calendar credentials configured (CALENDAR_CLIENT_ID, CALENDAR_CLIENT_SECRET, CALENDAR_REFRESH_TOKEN in .env)
  - [ ] Test event creation permission (can create events in Google Calendar)
  - [ ] Telegram bot running (if Telegram visibility step is included)
  
  ## Step 1: Create a Test Event via Helm
  - [ ] Via API or Telegram: Request weekly schedule for tomorrow
  - [ ] Example: "Create 2-hour meeting 14:00-16:00 UTC tomorrow"
  - [ ] Approve the proposal
  - Expected: Event created in Helm database
  
  ## Step 2: Verify Event Appears in Google Calendar
  - [ ] Open your Google Calendar in browser
  - [ ] Find the event created in Step 1
  - [ ] Confirm: event time matches Helm's proposal (14:00-16:00)
  - Expected: Event visible with correct start/end times
  
  ## Step 3: Manually Reschedule in Google Calendar (Create Drift)
  - [ ] In Calendar app, click the event
  - [ ] Edit: change start time to 15:00 (one hour later)
  - [ ] Save
  - Expected: Event now shows 15:00-17:00 in Calendar (different from Helm's 14:00-16:00)
  
  ## Step 4: Trigger Sync Reconciliation
  - [ ] Via API or internal tooling: run reconciliation step on the workflow
  - [ ] Or: wait up to 60 seconds for polling reconciliation to run (if enabled)
  - Expected: Reconciliation compares stored payload with live Calendar event
  
  ## Step 5: Verify Drift is Detected (Check Database/Logs)
  - [ ] Query: `SELECT * FROM workflow_sync_records WHERE status='drift_detected' ORDER BY created_at DESC LIMIT 1;`
  - [ ] Verify: recovery_classification = 'TERMINAL_FAILURE'
  - [ ] Verify: last_error_summary contains field_diffs (start time changed from 14:00 to 15:00)
  - [ ] Check logs: grep for "drift_detected" signal
  - [ ] Verify: logs show both stored and live fingerprints
  - Expected: Drift recorded durably; audit trail visible
  
  ## Step 6: Verify Drift Event Created
  - [ ] Query: `SELECT * FROM workflow_events WHERE event_type='drift_detected_external_change' ORDER BY created_at DESC LIMIT 1;`
  - [ ] Verify: details contains field_diffs (title, start, end changes)
  - [ ] Verify: details contains both fingerprints
  - [ ] Verify: details.sync_record_id matches from Step 5
  - Expected: Drift event is durable and queryable
  
  ## Step 7: Verify Recovery Action is Available
  - [ ] Call status API: GET /workflows/{run_id}
  - [ ] Verify: safe_next_actions includes "request_replay"
  - [ ] Verify: "retry" or "terminate" are NOT in safe_next_actions (passive policy)
  - [ ] Telegram (if enabled): Verify `/workflows` command shows "Request Replay" button
  - Expected: Operator can initiate recovery safely
  
  ## Step 8: Initiate Recovery (Request Replay)
  - [ ] Via API or Telegram: call request_replay on the drifted record/workflow
  - [ ] Example: POST /workflows/{run_id}/request_replay
  - [ ] Verify: response indicates replay enqueued
  - Expected: New sync lineage created
  
  ## Step 9: Verify Replay Execution (Mock or Live)
  - [ ] If using mocked adapter: verify test setup for replay scenario
  - [ ] If using live Calendar:
    - [ ] Trigger reconciliation again on new lineage
    - [ ] Helm's reconciliation will check the Calendar event (currently at 15:00)
    - [ ] Since your original intent (from Helm's proposal) was 14:00, replay will attempt to restore that
    - [ ] **Note:** If you want to preserve your manual edit (15:00), do NOT request replay; instead, update your Helm proposal for next week
  - Expected: New lineage executes; reconciliation confirms state
  
  ## Step 10: Verify No Silent Corruption
  - [ ] Query: `SELECT * FROM workflow_sync_records WHERE external_object_id='event_id_from_step2' ORDER BY lineage_generation DESC;`
  - [ ] Verify: multiple lineages present (original + replay)
  - [ ] Verify: old lineage shows DRIFT_DETECTED status (preserved)
  - [ ] Verify: new lineage shows terminal status (success or drift if still manually edited)
  - [ ] Verify: both lineages linked via idempotency_key
  - Expected: Full audit trail preserved; no data loss or silent overwrites
  
  ## Verification Summary
  - [ ] Drift was detected (Step 5)
  - [ ] Drift was recorded durably (Step 6)
  - [ ] Recovery action was available (Step 7)
  - [ ] Recovery was operator-initiated (Step 8)
  - [ ] Replay executed safely (Step 9)
  - [ ] No silent corruption (Step 10)
  - [ ] Audit trail is complete and queryable
  
  **All checks passed?** S04 is verified in your environment. Drift detection, recovery actions, and safe reconciliation are working correctly.
  ```

### 9. Run all tests and verify zero regressions
- Execute: `scripts/test.sh`
- Expected: All 5 new integration tests pass + all existing tests green
- Execute: `ruff check .`, `mypy packages/`, `black --check .`
- Expected: No linting violations

### 10. Verify observability signals
- Search logs for: "recovery_classification_assigned_to_drift", "drift_detected", "termination_after_partial_sync"
- Verify each integration test execution produces structured logs
- Document observability paths for S05 and operators

## Verification Checklist

- [ ] test_drift_detected_triggers_recovery_action passes (Scenario A)
- [ ] test_partial_failure_termination_preserves_state passes (Scenario B)
- [ ] test_mixed_outcomes_success_drift_pending passes (Scenario C)
- [ ] test_replay_after_drift_creates_new_lineage passes (Scenario D)
- [ ] test_multiple_syncs_some_drifted passes (Scenario E)
- [ ] All 5 tests verify safe_next_actions, recovery_classification, drift events
- [ ] All tests verify no silent corruption (audit trail, state transitions, lineage)
- [ ] UAT script is present and operator-readable
- [ ] UAT script covers: drift detection (Step 5), recovery action (Step 7), replay (Step 8), no corruption (Step 10)
- [ ] All queries in UAT script are correct SQL/API calls
- [ ] Full test suite passes (zero regressions)
- [ ] Linting passes (ruff, mypy, black)
- [ ] Observability signals present for all test scenarios

## Observability Impact

- All test scenarios produce structured logs:
  - "drift_detected" signal for Scenarios A, C, E
  - "termination_after_partial_sync" signal for Scenario B
  - "recovery_classification_assigned_to_drift" for all drifted records (from T01)
  - "request_replay_initiated" for Scenario D
- Database queries enable audit trail verification:
  - `workflow_sync_records` status transitions
  - `workflow_events` drift event creation and lineage
- Telegram (if enabled) shows recovery actions in status projection

## Done When

- T03 complete: All 5 integration scenarios pass; UAT script written and verified readable; zero regressions; observability signals captured.

