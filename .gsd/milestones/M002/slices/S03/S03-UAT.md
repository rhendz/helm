# S03: Task/calendar workflow protection and verification — UAT

**Milestone:** M002  
**Written:** 2026-03-13

## UAT Type

- UAT mode: **mixed** (automated tests + manual operator flow)
- Why this mode is sufficient: 
  - Automated tests (integration + unit) verify API/worker/Telegram contract semantics and catch regressions early
  - Manual UAT validates operator experience and end-to-end flow with real Postgres, API/worker/Telegram processes
  - Together they prove weekly scheduling works post-cleanup and remains operator-accessible

## Preconditions

### For Automated Tests

- Working Python environment with `uv run` and test dependencies installed
- Pytest suite available: `tests/integration/test_weekly_scheduling_end_to_end.py` and `tests/unit/test_workflow_telegram_commands.py`
- No external services required (tests use in-memory SQLite and mock adapters)

### For Manual UAT

- Fresh Postgres database or clean local SQLite: `rm -f helm.db`
- Alembic migrations applied: `uv run alembic upgrade head`
- API running on `http://localhost:8000` (or configured port)
- Worker running and able to execute workflow_runs jobs
- Telegram bot running (optional for this UAT; commands documented for reference)
- Representative request text and approval workflow understood (documented in phase 2)

## Smoke Test

Quick check that weekly scheduling still works after cleanup:

1. **Run integration tests** (should complete in <10 seconds):
   ```bash
   uv run --frozen --extra dev pytest -q tests/integration/test_weekly_scheduling_end_to_end.py
   # Expected: 3 tests PASS
   ```

2. **Expected output**:
   ```
   ...                                                           [100%]
   3 passed
   ```

If tests fail, do not proceed to manual UAT. Fix the regression first using `pytest -vv` to inspect assertion details.

## Test Cases

### 1. Integration Test: Happy-Path Weekly Scheduling (Automated)

**Purpose**: Verify the core weekly scheduling workflow operates end-to-end via API and worker semantics.

1. Run the integration test:
   ```bash
   uv run --frozen --extra dev pytest -v \
     tests/integration/test_weekly_scheduling_end_to_end.py::test_weekly_scheduling_end_to_end_happy_path
   ```

2. **Expected outcomes**:
   - API accepts POST /v1/workflow-runs with weekly_scheduling type and representative request text
   - Worker job processes dispatch_task_agent and dispatch_calendar_agent steps
   - Run transitions to await_schedule_approval with approval checkpoint created
   - API approval route accepts POST /v1/workflow-runs/{id}/approve
   - Orchestration service executes sync records (6 total: 3 task_upsert, 3 calendar_block_upsert)
   - Run reaches status=completed with completion_summary (headline, approval_decision, downstream_sync_status, sync counts)
   - Test assertions all pass

3. **If test fails**:
   - Run with verbose output: `pytest -vv ...::test_weekly_scheduling_end_to_end_happy_path`
   - Check assertion message and compare actual vs. expected values
   - Likely causes: API response schema changed, worker job skipped a step, sync record linkage broken
   - If regression confirmed, note in Known Issues section

### 2. Integration Test: Approval Checkpoint Blocking (Automated)

**Purpose**: Verify runs correctly block at approval checkpoints and resume cleanly after approval.

1. Run the checkpoint test:
   ```bash
   uv run --frozen --extra dev pytest -v \
     tests/integration/test_weekly_scheduling_end_to_end.py::test_weekly_scheduling_approval_checkpoint_blocks_execution
   ```

2. **Expected outcomes**:
   - Run created and advanced to await_schedule_approval step
   - Approval checkpoint record created with target_artifact_id and proposal_summary
   - paused_state is awaiting_approval (run is blocked)
   - Worker does not proceed past approval checkpoint without approval action
   - After approval, run resumes to apply_schedule step
   - Test assertions pass (idempotency confirmed, no duplicate approvals)

3. **If test fails**:
   - Check approval checkpoint creation logic
   - Verify paused_state transitions are correct
   - Inspect test assertion for which condition failed

### 3. Integration Test: Sync Record Integrity (Automated)

**Purpose**: Verify sync records are created correctly and linked to completion summary.

1. Run the sync integrity test:
   ```bash
   uv run --frozen --extra dev pytest -v \
     tests/integration/test_weekly_scheduling_end_to_end.py::test_weekly_scheduling_sync_record_integrity
   ```

2. **Expected outcomes**:
   - After apply_schedule, sync records created with correct sync_kind (task_upsert, calendar_block_upsert)
   - All sync records have status=succeeded
   - Completion summary total_sync_writes matches count of sync records (should be 6)
   - task_sync_writes = 3, calendar_sync_writes = 3
   - Lineage and artifact linkage preserved
   - Test assertions pass

3. **If test fails**:
   - Check sync record creation in orchestration service
   - Verify sync_kind enum values match database schema
   - Inspect completion_summary field population logic

### 4. Unit Test: Telegram Completion Summary (Automated)

**Purpose**: Verify Telegram command formatting correctly surfaces completion summaries.

1. Run the Telegram test:
   ```bash
   uv run --frozen --extra dev pytest -v \
     tests/unit/test_workflow_telegram_commands.py::test_workflow_completion_summary_surfaces_sync_counts
   ```

2. **Expected outcomes**:
   - Telegram /workflow command formats completion summary with outcome headline
   - Sync write counts displayed: "Sync: X total (Y task, Z calendar) succeeded"
   - Scheduled highlights and carry-forward tasks included
   - Test assertions pass

3. **If test fails**:
   - Check _format_run() function in workflows.py for completion_summary formatting
   - Verify field names match API response schema (not internal database names)
   - Review test assertion to see which field is missing or incorrect

### 5. Unit Test: Telegram Approval Checkpoint (Automated)

**Purpose**: Verify Telegram correctly displays approval checkpoints.

1. Run the checkpoint test:
   ```bash
   uv run --frozen --extra dev pytest -v \
     tests/unit/test_workflow_telegram_commands.py::test_workflow_approval_checkpoint_shows_artifact_and_proposal
   ```

2. **Expected outcomes**:
   - Telegram displays approval checkpoint with target artifact ID and version
   - Proposal summary included
   - Instructions to reference artifact ID in approval commands clear
   - Test assertions pass

3. **If test fails**:
   - Check approval_checkpoint formatting in _format_run()
   - Verify artifact_id and version fields are present in checkpoint response
   - Review test assertion

### 6. Manual UAT: End-to-End Weekly Scheduling Flow (Live Runtime)

**Purpose**: Verify operator can follow concrete steps to create, approve, and complete a weekly scheduling run.

**Preconditions**:
- Fresh environment: `rm -f helm.db && uv run alembic upgrade head`
- API, worker running in separate terminals
- Curl or API client available
- Representative request text available (see Phase 2 in `.gsd/milestones/M002/slices/S03/uat.md`)

**Steps** (follow exactly as documented in `uat.md`):

1. **Phase 1: Stack Startup**
   - Start API: `bash scripts/run-api.sh`
   - Start worker: `bash scripts/run-worker.sh`
   - Verify both listening and processing cleanly

2. **Phase 2: Create Weekly Scheduling Run**
   - POST to /v1/workflow-runs with representative request text
   - Capture run_id from response
   - Verify response includes workflow_type=weekly_scheduling, status=active

3. **Phase 3: Proposal Generation**
   - Worker processes; wait for run to block at await_schedule_approval
   - GET /v1/workflow-runs/{run_id} and verify:
     - status=active (not completed yet)
     - paused_state=awaiting_approval
     - current_step_type=await_schedule_approval
   - GET /v1/workflow-runs/{run_id}/proposal-versions and verify proposal exists with 3 task blocks

4. **Phase 4: Approval**
   - POST /v1/workflow-runs/{run_id}/approve with artifact_id from proposal
   - Verify response shows approved_at timestamp
   - GET /v1/workflow-runs/{run_id} and verify:
     - paused_state is now null (unblocked)
     - current_step_type=apply_schedule

5. **Phase 5: Sync Execution**
   - Worker processes; wait for sync to complete
   - GET /v1/workflow-runs/{run_id} and verify:
     - status=completed
     - completion_summary.headline contains "Scheduled X block(s) and synced Y approved write(s)"
     - completion_summary.total_sync_writes = 6 (or expected count)
   - Database inspection (optional): query workflow_sync_records and verify 6 records with status=succeeded

6. **Phase 6: Verify Replay (Optional)**
   - GET /v1/workflow-runs/{run_id}/completion-summary/safe-next-actions
   - Verify request_replay is an available action
   - Optionally: POST /v1/workflow-runs/{run_id}/request-replay to exercise replay path

7. **Expected outcomes**:
   - All curl commands succeed with expected response codes (200, 201)
   - Responses include expected fields (run_id, status, completion_summary, proposal)
   - Database contains correct workflow_runs, workflow_sync_records, workflow_approval_checkpoints rows
   - Workflow reaches completion without errors
   - Operator can visually confirm output matches documented expectations

**If manual UAT fails**:
- Check API logs for errors (500s, validation failures)
- Check worker logs for job processing issues
- Compare actual responses against `.gsd/milestones/M002/slices/S03/uat.md` documented examples
- Debug using database inspection queries from UAT script

### 7. Restart-Safe Resume Verification (Optional Advanced)

**Purpose**: Confirm weekly scheduling workflows can safely resume if worker restarts mid-sync.

**Preconditions**: Completed phase 5 above (run in sync execution phase).

**Steps**:

1. Create a fresh weekly scheduling run (phases 1-3)
2. Approve the proposal (phase 4)
3. **Before** worker finishes sync: observe sync records being created, then kill the worker: `pkill -f "python.*run-worker"`
4. Verify run state: GET /v1/workflow-runs/{id} shows status=active, current_step_type=apply_schedule
5. Restart worker: `bash scripts/run-worker.sh`
6. Wait for sync to resume and complete
7. Verify final state:
   - Run reaches status=completed (not duplicate or error state)
   - Completion summary is correct and matches first time
   - Sync records created exactly once (no duplicates)

**Expected outcome**: Worker resumes cleanly without duplication or errors. Database unique constraints on workflow_sync_records prevent duplicate sync writes.

**If restart resume fails**:
- Check sync_kind and other unique constraint fields in schema
- Verify idempotency logic in orchestration service
- Review worker job error logs for resume errors

## Edge Cases

### Edge Case 1: Rejection of Proposal

**Purpose**: Verify proposal can be rejected and run returns to waiting for new proposal.

1. Create run and advance to await_schedule_approval (phases 1-3)
2. POST /v1/workflow-runs/{id}/reject with artifact_id
3. Verify response shows rejected_at timestamp
4. GET /v1/workflow-runs/{id} and verify:
   - status is still active (not failed)
   - paused_state should allow restarting proposal generation
5. Worker resumes and generates a new proposal (or run waits for manual action, depending on logic)

**Expected**: Rejection is recorded, run does not fail, operator can take next action.

### Edge Case 2: Request Revision of Proposal

**Purpose**: Verify operator can request revision and proposal regenerates.

1. Create run and advance to await_schedule_approval (phases 1-3)
2. POST /v1/workflow-runs/{id}/request-revision with revision_feedback (e.g., "consolidate duplicate tasks")
3. Verify response shows requested_revision_at timestamp
4. GET /v1/workflow-runs/{id} and verify:
   - status is still active
   - paused_state allows regeneration or waits for next cycle
5. Worker resumes and generates revised proposal (if logic supports immediate regeneration)

**Expected**: Revision request recorded, proposal regenerated with feedback considered (or queued for next cycle).

### Edge Case 3: Partial Sync Failure

**Purpose**: Verify behavior if a single sync write fails.

**Note**: Current M002 implementation does not test partial failure scenarios. This is documented as a future enhancement. For now, assume all syncs succeed (stubs return success). If this UC occurs in real use, a new integration test should be added to verify failure handling.

**Expected**: Sync records created with status values reflecting success/failure; completion_summary includes failure count.

## Failure Signals

The following would indicate something is broken:

- **Test assertion failure**: Any of the 14 automated tests fail (integration or unit). This is the primary regression detector.
- **API response mismatch**: Manual UAT step receives unexpected response code (not 200/201) or response fields missing (e.g., completion_summary absent when expected).
- **Worker stalls**: Worker process stops responding or workflow_runs job fails with exceptions (look for "relation does not exist" which is expected for non-truth agents, but actual errors would be different).
- **Database inconsistency**: workflow_sync_records count does not match completion_summary.total_sync_writes; approval_checkpoint without valid target_artifact_id.
- **Telegram format breaks**: Unit tests fail when completion_summary or approval_checkpoint formatting changes unexpectedly.
- **Restart failure**: Worker resumes after crash and creates duplicate sync records or fails to complete the run.

Any of these warrant immediate investigation before proceeding to next milestone.

## Requirements Proved By This UAT

- **R003 — Task/calendar workflows remain intact and verified after cleanup**: UAT proves weekly scheduling workflow runs end-to-end via API/worker/Telegram after M002 cleanup (S01 truth set, S02 artifact removal). Approval checkpoints, sync execution, and completion summaries all function correctly.

## Not Proven By This UAT

- **Live Telegram bot interaction**: Telegram commands are tested via unit mocks but not live-tested against real Telegram chat. A future UAT with real bot credentials can prove this.
- **Email/Study agent workflows**: M002 treats EmailAgent and StudyAgent as non-truth; these are not tested or verified in S03. Future milestones can add workflows for these agents.
- **Multi-user concurrent workflows**: UAT tests single operator, single run. Concurrent run handling is not tested (though database constraints and worker semantics should support it).
- **Extended retry and recovery scenarios**: Partial failures, network timeouts, and long-lived restart scenarios are not fully explored.

## Notes for Tester

1. **Legacy job errors are expected**: Worker logs will show failures from email_deep_seed, email_triage, scheduled_thread_tasks jobs. This is correct per M002 truth note—these agents are non-truth and their tables don't exist. Ignore these errors. Only workflow_runs job should process cleanly.

2. **Database file**: Local SQLite creates `helm.db` in the project root. Delete it to start fresh: `rm -f helm.db`.

3. **Port conflicts**: Ensure port 8000 (API), 5433 (Postgres, if using), and other service ports are available before starting.

4. **Test ordering**: Run automated tests first (they're fast and isolated). Only proceed to manual UAT if tests pass.

5. **Curl syntax**: Manual UAT uses curl examples. If curl is not available, use Postman, Python requests, or equivalent. Just ensure Content-Type headers are set correctly (application/json).

6. **Response inspection**: Use `jq` to pretty-print JSON responses from curl: `curl ... | jq .` to see field names clearly.

7. **No Telegram secrets needed**: This UAT does not require Telegram credentials. Unit tests use mocks. Live Telegram testing is a future enhancement.

8. **Documentation reference**: Detailed commands and expected outputs are in `.gsd/milestones/M002/slices/S03/uat.md`. Use that as the primary reference while executing.
