---
estimated_steps: 7
estimated_files: 3
---

# T03: Add integration test covering drift detection end-to-end and document polling strategy decision

**Slice:** S02 — External-Change Detection and Sync State Reconciliation
**Milestone:** M003

## Description

Create a comprehensive integration test (TestEndToEndDriftWorkflow) that exercises the full drift detection flow: write a calendar event via the real adapter from S01, simulate a manual operator reschedule (fingerprint changes), trigger orchestration reconciliation, and verify drift is detected, state is updated, and events are created. Also append the polling strategy decision to DECISIONS.md so future slices understand the latency and API cost assumptions.

The integration test uses the real GoogleCalendarAdapter from S01 (or mocked to return specific fingerprints) and exercises both the adapter and orchestration layers together.

## Steps

1. Create new file `tests/integration/test_drift_detection_and_reconciliation.py` with fixture setup (test database, orchestration service, mocked calendar adapter)
2. Build TestEndToEndDriftWorkflow test class with:
   - Setup: create a workflow run with a calendar sync record (UNCERTAIN_NEEDS_RECONCILIATION status, with stored fingerprint)
   - Mock the calendar adapter's reconcile_calendar_block() to return SyncLookupResult with payload_fingerprint_matches=False and live_event_details showing manually edited time
   - Call orchestration._sync_execution_step() to trigger reconciliation
   - Assert: sync record status is now DRIFT_DETECTED
   - Assert: workflow event created with type "drift_detected_external_change" and field diffs in details
   - Assert: logs contain "drift_detected" signal
3. Add TestReconciliationStateUpdate class with simpler unit-like tests: just drift case, verify mark_drift_detected called correctly, event created with correct schema
4. Verify field diffs are correct in the event details (title, start, end extracted and compared)
5. Add a test for the "found but fingerprint_matches" case (reconciliation succeeds, event not created, marked as SUCCEEDED) to cover the happy path in the updated method
6. Append decision to .gsd/DECISIONS.md:
   - "Drift detection via continuous polling (not webhooks)."
   - "Polling interval: 60 seconds during active sync phases."
   - "Rationale: simpler infrastructure (no webhook endpoints, no Google signature validation), acceptable API quota impact for infrequent manual edits."
   - "Fingerprint fields included in drift detection: title, start, end, description."
   - "Fingerprint schema evolution: adding new fields requires fingerprint version bump to avoid false drifts."
   - "Can be evolved to webhooks if operator workflows create frequent drift."
7. Run full test suite and lint (ruff, black, mypy)

## Must-Haves

- [ ] `tests/integration/test_drift_detection_and_reconciliation.py` created with comprehensive drift test
- [ ] TestEndToEndDriftWorkflow covers: write event, simulate manual reschedule, reconcile, verify DRIFT_DETECTED, event created, logs signal
- [ ] TestReconciliationStateUpdate covers drift case specifically with field diffs assertion
- [ ] Test for "found and fingerprint_matches" case (reconciliation succeeds, event not created)
- [ ] Field diffs correctly extracted and compared (title, start, end at minimum)
- [ ] Polling strategy decision appended to DECISIONS.md with rationale and constraints documented
- [ ] All integration tests pass (new and existing)
- [ ] All existing tests pass (zero regressions)
- [ ] Ruff, mypy, black all pass

## Verification

- Run `pytest tests/integration/test_drift_detection_and_reconciliation.py::TestEndToEndDriftWorkflow -v` — passes
- Run `pytest tests/integration/test_drift_detection_and_reconciliation.py::TestReconciliationStateUpdate -v` — passes
- Run `pytest tests/integration/test_drift_detection_and_reconciliation.py -v` — all tests pass
- Run `pytest tests/integration/ -v` — all integration tests pass (zero regressions)
- Run `scripts/test.sh` — full suite passes
- Verify DECISIONS.md contains polling decision with rationale, fingerprint fields, and evolution path
- Grep test output for "drift_detected" log signals: `pytest tests/integration/test_drift_detection_and_reconciliation.py -s | grep drift_detected` — present
- Run `ruff check tests/integration/test_drift_detection_and_reconciliation.py` — no errors
- Run `mypy tests/` — no type errors for new test file

## Observability Impact

- Integration tests log all drift detection steps, making it easy for future agents to understand the flow
- Test assertions on both state (sync record status, event type, field diffs) and observability (logs)
- Failure state: if test fails, full log output shows where drift detection broke

## Inputs

- `packages/orchestration/src/helm_orchestration/workflow_service.py` — _sync_execution_step() method to understand the orchestration flow
- `packages/connectors/src/helm_connectors/google_calendar.py` — GoogleCalendarAdapter from S01 for reference on field diffs extraction
- `.gsd/DECISIONS.md` — append-only decision register
- M003 research document (already preloaded) — polling strategy recommendation and fingerprint field list

## Expected Output

- Comprehensive integration test file (`tests/integration/test_drift_detection_and_reconciliation.py`) with 3+ tests
- All tests passing, proving drift detection works end-to-end
- Polling strategy decision documented in DECISIONS.md with clear assumptions and evolution path
- Zero regressions in existing tests
- Full test suite green
