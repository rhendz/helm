---
status: done
blocker_discovered: false
summary_confidence: high
observability_surfaces:
  - Integration test output: `pytest -q tests/integration/test_weekly_scheduling_end_to_end.py` result counts and pass/fail signals
  - Test assertion messages: assertions fail with clear context when approval checkpoints, sync records, or completion summaries regress
  - Database state inspection via fixtures: WorkflowRunRepository, WorkflowSyncRecordRepository queries for verification
  - Worker job logs in test context: monkeypatch captures `workflow_runs_job.run()` effects on database
  - Test file itself documents expected flow: `test_weekly_scheduling_end_to_end_happy_path` comments trace each phase
---

# T02 Summary: Add/extend integration test for weekly scheduling end-to-end

## What Was Done

Created a comprehensive integration test file (`tests/integration/test_weekly_scheduling_end_to_end.py`) that exercises the representative weekly scheduling / task+calendar workflow end-to-end via API and worker semantics. The test provides automated verification and guardrails for the core workflow behavior after M002 cleanup.

### Deliverables

1. **Integration test file** — `tests/integration/test_weekly_scheduling_end_to_end.py` (367 lines)
   - **`test_weekly_scheduling_end_to_end_happy_path`**: Full happy-path test covering create → proposal → approval → apply_schedule → sync → completion
   - **`test_weekly_scheduling_approval_checkpoint_blocks_execution`**: Verifies approval checkpoint blocking behavior and idempotency
   - **`test_weekly_scheduling_sync_record_integrity`**: Validates sync record creation and completion summary linkage

2. **Test Coverage**

   - **API routes tested**: POST /v1/workflow-runs, GET /v1/workflow-runs/{id}, GET /v1/workflow-runs/{id}/proposal-versions, POST /v1/workflow-runs/{id}/approve
   - **Worker job wiring**: Uses actual `workflow_runs_job.run()` to advance dispatch_task_agent and dispatch_calendar_agent steps
   - **Orchestration service**: Integrates `WorkflowOrchestrationService.execute_pending_sync_step()` for sync execution
   - **Repository layer**: Queries `SQLAlchemyWorkflowSyncRecordRepository` to verify sync record creation and linkage

3. **Assertions Cover Must-Haves**

   - ✅ Full weekly scheduling happy path: create → proposal → approval → apply_schedule → sync
   - ✅ Approval checkpoint creation with required fields (target_artifact_id, proposal_summary, allowed_actions)
   - ✅ Schedule proposal artifacts linked to sync records via workflow run
   - ✅ Completion summary fields (headline, approval_decision, downstream_sync_status, total_sync_writes, task/calendar split)
   - ✅ Sync record integrity: both task_upsert and calendar_block_upsert records created with status=succeeded
   - ✅ Lineage final summary linkage: approval_decision preserved, downstream_sync_reference_ids matches source records

4. **Test Fixtures and Helpers**
   - `_client()`: Generator providing in-memory SQLite session with TestClient (mirrors existing pattern from test_workflow_status_routes.py)
   - `_SessionContext`: Context manager for monkeypatch compatibility with worker job functions
   - `_validator_registry()`: Minimal validator registry for workflow execution

### Alignment with UAT Script

The test directly mirrors the UAT script flow from `.gsd/milestones/M002/slices/S03/uat.md`:
- Request text uses the same representative weekly scheduling example (task planning with constraints)
- Workflow state transitions match documented expected outcomes at each phase
- Completion summary fields align with documented response structure
- Sync record creation verified against documented expected counts

### Verification Status

#### Must-Haves

- [x] **Integration test covers a full weekly scheduling happy path via API + worker semantics**
  - Test creates run via POST /v1/workflow-runs with weekly_scheduling type
  - Worker jobs advance through dispatch_task_agent and dispatch_calendar_agent
  - Run blocks at await_schedule_approval with approval checkpoint
  - Approval via POST /v1/workflow-runs/{id}/approve
  - Sync executed via orchestration service execute_pending_sync_step()
  - Run completes with status=completed

- [x] **Test asserts on both kernel-level behavior and operator-facing projections**
  - **Kernel-level**: Approval checkpoints created with target_artifact_id and version_number; sync records exist with correct sync_kind (task_upsert, calendar_block_upsert) and status (succeeded)
  - **Operator-facing**: Completion summary fields (headline, approval_decision, downstream_sync_status, total_sync_writes, task_sync_writes, calendar_sync_writes) correctly populated and match stored sync records

#### Test Execution

```
uv run --frozen --extra dev pytest -q tests/integration/test_weekly_scheduling_end_to_end.py
```

Result: **All 3 tests PASS**
- test_weekly_scheduling_end_to_end_happy_path ✓
- test_weekly_scheduling_approval_checkpoint_blocks_execution ✓
- test_weekly_scheduling_sync_record_integrity ✓

Full integration test suite also passes: `pytest -q tests/integration/` — 8 tests PASS

### Intentional Invariant Breakage (Verification)

Tested breaking a key invariant to confirm test catches regressions:
- Modified `completion_summary["total_sync_writes"]` assertion from `> 0` to `== 0` 
- Test correctly failed with clear assertion error, signaling regression detection works

### Design Notes

1. **Fixture Pattern**: Follows existing `test_workflow_status_routes.py` structure for consistency and compatibility with the API test infrastructure.

2. **Worker Integration**: Uses monkeypatch to override `SessionLocal` in workflow_runs_job and replay_service, enabling worker execution against test database without external dependencies.

3. **Orchestration Service**: Instantiated with StubTaskSystemAdapter and StubCalendarSystemAdapter for deterministic sync record creation without external system calls.

4. **Sync Kind Values**: Uses actual enum values (task_upsert, calendar_block_upsert) instead of descriptive names to match database schema.

5. **No Replay Coverage**: The first test (happy path) focuses on the core weekly scheduling flow. Replay testing is covered by existing `test_public_representative_flow_reaches_completion_and_replay_with_fresh_final_summary` in the workflow status routes test.

### Files Modified

- `tests/integration/test_weekly_scheduling_end_to_end.py` — Created (367 lines)
- `.gsd/milestones/M002/slices/S03/tasks/T02-PLAN.md` — Added Observability Impact section (during pre-flight)

### Decisions

No new architectural or pattern decisions required. The test follows established patterns from existing integration test suite.

## Diagnostics

To inspect what this task built and verify integration test behavior:

1. **Run the integration test and inspect output**:
   ```bash
   uv run --frozen --extra dev pytest -v \
     tests/integration/test_weekly_scheduling_end_to_end.py
   # Should show 3 tests PASS with clear assertion messages
   ```

2. **Check test file structure and assertions**:
   ```bash
   grep -n "def test_\|assert " tests/integration/test_weekly_scheduling_end_to_end.py | head -20
   # Shows test names and key assertions
   ```

3. **Verify fixtures and helper functions**:
   ```bash
   grep -n "def _client\|def _SessionContext\|def _validator_registry" \
     tests/integration/test_weekly_scheduling_end_to_end.py
   ```

4. **Inspect sync record creation in the test**:
   ```bash
   grep -A5 "sync_records = " tests/integration/test_weekly_scheduling_end_to_end.py
   # Shows verification of sync record counts (should be 6: 3 task, 3 calendar)
   ```

5. **Compare test flow with UAT script**:
   ```bash
   # T02 integration test follows the same phases as T01 UAT script
   grep "# Phase\|workflow_runs_job.run()" tests/integration/test_weekly_scheduling_end_to_end.py
   
   # UAT phases for reference
   grep "^## Phase" .gsd/milestones/M002/slices/S03/uat.md
   ```

6. **Run test in failure mode to verify detection**:
   - Edit test: change `assert len(sync_records) == 6` to `assert len(sync_records) == 0`
   - Run test: `uv run --frozen --extra dev pytest -v tests/integration/test_weekly_scheduling_end_to_end.py`
   - Observe clear failure signal (test name + assertion error)
   - Revert change and re-run to confirm it passes again

7. **Verify worker job integration**:
   ```bash
   # Check that workflow_runs_job.run() is called in the test
   grep "workflow_runs_job.run()" tests/integration/test_weekly_scheduling_end_to_end.py
   
   # Inspect job source to understand what it does
   grep -n "def run(" apps/worker/src/helm_worker/jobs/workflow_runs.py | head -1
   ```

## Next Steps

The test is ready for inclusion in slice verification. It provides:
- Automated verification that weekly scheduling workflows function end-to-end
- Early detection of regressions in approval checkpoints, sync records, or completion summary generation
- Reference implementation for operators/future maintenance of weekly scheduling features

The corresponding UAT script from T01 can now be executed manually to verify the same flow with real API/worker/Telegram interaction.
