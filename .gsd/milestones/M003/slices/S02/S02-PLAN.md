# S02: External-Change Detection and Sync State Reconciliation

**Goal:** Detect when an operator manually reschedules a Calendar event that Helm wrote, update internal state to reflect the external change as truth, and create observable workflow events for downstream recovery actions.

**Demo:** Operator manually reschedules a Calendar event written by Helm; Helm detects the manual edit via fingerprint comparison; internal `workflow_sync_records` is updated with new state marked as DRIFT_DETECTED; a workflow event `drift_detected_external_change` is created with rich details (both fingerprints, field diffs); logs contain authoritative drift-detection signals for inspection.

## Must-Haves

- DRIFT_DETECTED status added to `WorkflowSyncStatus` enum
- Orchestration service extends `_reconcile_sync_record()` to handle fingerprint mismatch (drift case)
- When drift detected: sync record marked with DRIFT_DETECTED status, workflow event created, logs emitted
- Drift event includes both stored and live fingerprints, extracted field diffs (title, start, end)
- Polling strategy decision (continuous polling, 60-second interval) documented in DECISIONS.md
- Integration test proves drift detection end-to-end: write event, manually reschedule (simulated), detect drift, reconcile state
- All existing tests continue to pass (zero regressions)

## Proof Level

- This slice proves: **integration** (drift detection logic integrated into orchestration and tested with real adapter from S01)
- Real runtime required: yes (real Google Calendar adapter from S01 participates)
- Human/UAT required: no (automated tests sufficient; S05 UAT will verify operator experience)

## Verification

- `tests/integration/test_drift_detection_and_reconciliation.py::TestDriftDetection` — drift detection with fingerprint mismatch
- `tests/integration/test_drift_detection_and_reconciliation.py::TestReconciliationStateUpdate` — sync record status transition and event creation
- `tests/integration/test_drift_detection_and_reconciliation.py::TestEndToEndDriftWorkflow` — full workflow: write event, simulate manual edit, detect drift, reconcile state
- Grep logs for `drift_detected` signal in all integration tests
- All existing tests pass (`scripts/test.sh`)

## Observability / Diagnostics

- Runtime signals: `drift_detected` log when fingerprints don't match; `mark_drift_detected` operation timing
- Inspection surfaces: database query `SELECT * FROM workflow_sync_records WHERE status='drift_detected'` shows all detected drifts; logs grep `drift_detected` with both fingerprints
- Failure visibility: drift event stored durably in `workflow_events` table with full fingerprint and field diff details
- Redaction constraints: none (fingerprints are not PII; event details are debug-only, never exposed to operator UI directly)

## Integration Closure

- Upstream surfaces consumed: `GoogleCalendarAdapter.reconcile_calendar_block()` from S01, `WorkflowOrchestrationService._reconcile_sync_record()` entry point, sync record repository and event repository
- New wiring introduced in this slice: orchestration service now handles drift case in `_reconcile_sync_record()`, creates drift events, marks sync records with DRIFT_DETECTED status
- What remains before the milestone is truly usable end-to-end: S03 projects drift events to Telegram (making operator aware), S04 adds recovery policy (passive observation vs active proposal)

## Tasks

- [x] **T01: Extend sync record state machine with DRIFT_DETECTED status and drift marking method** `est:45m`
  - Why: Durable state machine needs a status value to mark drift detection. Adding the status and a helper method establishes the state-update foundation.
  - Files: `packages/storage/src/helm_storage/repositories/contracts.py`, `packages/storage/src/helm_storage/repositories/workflow_sync_records.py`
  - Do: Add DRIFT_DETECTED to WorkflowSyncStatus enum. Add mark_drift_detected(sync_record_id, live_fingerprint, field_diffs) method to sync record repo. Method should update status to DRIFT_DETECTED, mark completed_at, and optionally update a durable field with the live fingerprint and field diff details. Use existing WorkflowSyncRecordPatch pattern for the update. Write unit tests for the new method (happy path, sync record not found, exception on failed update).
  - Verify: `pytest tests/unit/test_workflow_sync_records.py::TestMarkDriftDetected` passes
  - Done when: DRIFT_DETECTED status in enum, mark_drift_detected() method works, unit tests pass (3 tests minimum)

- [x] **T02: Implement drift detection and reconciliation state update in orchestration service** `est:1h`
  - Why: Orchestration owns the reconciliation control flow. When drift is detected (fingerprint mismatch from S01 adapter), orchestration must update state, create workflow event, and log clearly.
  - Files: `packages/orchestration/src/helm_orchestration/workflow_service.py`, `packages/orchestration/src/helm_orchestration/schemas.py`
  - Do: Extend `_reconcile_sync_record()` method to check `reconciliation.payload_fingerprint_matches`. If False (drift detected): (1) log drift event with both stored fingerprint and live fingerprint; (2) extract field diffs from live event details (title, start, end); (3) create NewWorkflowEvent with type `drift_detected_external_change` including fingerprints and field diffs in details; (4) mark sync record with mark_drift_detected(); (5) continue to next record instead of failing or marking as succeeded. Ensure logs emit "drift_detected" signal for grep diagnostics. Field diff extraction: compare stored payload against reconciliation.live_event_details (or equivalent) to extract which fields changed.
  - Verify: `pytest tests/integration/test_drift_detection_and_reconciliation.py::TestReconciliationStateUpdate` passes; logs contain "drift_detected" signal
  - Done when: Drift case fully handled in orchestration, workflow event created, sync record marked, logs emitted, integration test passes

- [x] **T03: Add integration test covering drift detection end-to-end and document polling strategy decision** `est:1h15m`
  - Why: Proves the full flow works: adapter detects drift via fingerprint comparison, orchestration responds by updating state and creating events. Also documents the polling strategy choice in DECISIONS.md so future slices understand the cost/latency tradeoff.
  - Files: `tests/integration/test_drift_detection_and_reconciliation.py`, `.gsd/DECISIONS.md`
  - Do: Create new integration test file with TestEndToEndDriftWorkflow class. Test: (1) create calendar event via upsert_calendar_block (real adapter from S01); (2) verify event created and sync record has external_object_id; (3) simulate manual operator edit by directly modifying the live event fingerprint in the reconciliation mock/fixture (pretend operator rescheduled); (4) run orchestration sync step that hits UNCERTAIN_NEEDS_RECONCILIATION and triggers reconcile; (5) verify drift is detected, sync record marked DRIFT_DETECTED, workflow event created with field diffs; (6) verify logs contain "drift_detected". For the orchestration test, use mocked GoogleCalendarAdapter returning SyncLookupResult with payload_fingerprint_matches=False (and live event details showing new start time, for example). Append decision to DECISIONS.md: "Drift detection via continuous polling (not webhooks). Polling interval: 60 seconds during active sync phases. Rationale: simpler infrastructure, acceptable API quota impact for infrequent manual edits. Future evolution: can move to webhooks if operator workflows create frequent drift." Also document fingerprint fields (title, start, end, description) and note that adding fields requires fingerprint version bump.
  - Verify: `pytest tests/integration/test_drift_detection_and_reconciliation.py::TestEndToEndDriftWorkflow` passes; DECISIONS.md contains polling decision; `scripts/test.sh` passes (all tests)
  - Done when: Integration test passes, decision documented, all tests green

## Files Likely Touched

- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/schemas.py` (possibly, for field diff schema if needed)
- `tests/integration/test_drift_detection_and_reconciliation.py` (new file)
- `.gsd/DECISIONS.md`
