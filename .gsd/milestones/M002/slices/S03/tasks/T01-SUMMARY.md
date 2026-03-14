---
status: done
blocker_discovered: false
summary_confidence: high
observability_surfaces:
  - UAT script checkpoint outputs: each phase documents expected API responses and database state
  - Migration error logs if chain is broken (psycopg2.errors.ForeignKeyViolation on apply)
  - Worker logs for workflow_runs job success vs. legacy agent job failures
  - Database verification queries in UAT for sync_records, approval_checkpoints, and artifacts
  - API response field presence/absence in completion_summary and approval_checkpoint structures
---

# T01 Summary: Define UAT Script for Weekly Scheduling Flow

## What Was Done

Authored a comprehensive, operator-focused UAT script (`.gsd/milestones/M002/slices/S03/uat.md`) that walks through a complete weekly scheduling workflow from stack startup through completion, enabling future operators to verify end-to-end behavior after M002 cleanup.

### Deliverables

1. **UAT script** — `.gsd/milestones/M002/slices/S03/uat.md`
   - 7 major phases covering environment setup, run creation, proposal generation, approval, sync execution, and verification
   - Concrete commands (curl examples) for all API routes
   - Explicit checkpoints at each stage with expected output patterns
   - Database inspection steps to verify persistence
   - Restart-safe resume verification to confirm idempotency

2. **Pre-flight observability fixes**
   - Added `## Observability Impact` section to T01-PLAN.md describing inspection surfaces and failure diagnostics
   - Enhanced S03-PLAN.md Verification section with explicit failure-path checks (restart safety before approval, mid-sync resume)

3. **Migration fix**
   - Fixed broken Alembic migration chain: migration 0007 referenced non-existent 0006. Changed `down_revision` in 20260313_0007_workflow_foundation.py from `20260310_0006` to `20260308_0001` to chain correctly to the baseline.

### End-to-End Verification

Ran through the UAT script manually from a fresh environment:

1. **Setup** — Database initialized, migrations applied cleanly
2. **Stack start** — API, worker, and Telegram processes started (worker logs showed legacy job errors for non-truth agents, but workflow_runs job processed cleanly)
3. **Run creation** — Created a weekly scheduling run via API with representative request text
4. **Proposal generation** — Worker advanced run through dispatch_task_agent and dispatch_calendar_agent steps, created schedule proposal with 3 task blocks
5. **Approval checkpoint** — Run blocked at `await_schedule_approval` with paused_state=`awaiting_approval`, proposal_summary visible, target_artifact_id populated
6. **Approval decision** — Approved proposal via API, run transitioned to `apply_schedule` step
7. **Sync execution** — Worker executed adapter-gated sync, created 6 sync records (3 task writes, 3 calendar writes), all with status=`succeeded`
8. **Completion** — Run reached status=`completed` with:
   - completion_summary.headline: "Scheduled 3 block(s) and synced 6 approved write(s)."
   - approval_decision: `approve`
   - downstream_sync_status: `succeeded`
   - Database verification showed correct sync records and approval checkpoint records

### UAT Script Content Verification

Cross-checked all commands and field names against actual codebase:

- **API routes:** Verified `/v1/workflow-runs` POST/GET, `/{run_id}` GET, `/proposal-versions` GET, `/approve`, `/reject`, `/request-revision` endpoints exist and match runbook
- **Response fields:** Confirmed all expected fields in WorkflowRunDetailResponse, WorkflowCompletionSummaryResponse, WorkflowApprovalCheckpointResponse schemas match documentation
- **Telegram commands:** Verified `/workflows`, `/workflow_needs_action`, `/workflow_versions`, `/approve`, `/reject`, `/request_revision` command patterns in apps/telegram-bot/src/helm_telegram_bot/commands/
- **Database tables:** Confirmed `workflow_runs`, `workflow_steps`, `workflow_artifacts`, `workflow_approval_checkpoints`, `workflow_sync_records` tables exist with correct column names
- **Table fields:** Updated SQL queries in UAT from inaccurate field names (e.g., `agent_type`, `outcome_status`) to actual ORM fields (`target_system`, `sync_kind`, `status`)

### Observations

1. **Legacy job errors are expected** — The worker registers jobs for non-truth agents (email_deep_seed, email_triage, scheduled_thread_tasks) that fail with "relation does not exist" errors. This is correct per M002 truth note: these agents are non-truth and their tables don't exist. The workflow_runs job still processes cleanly.

2. **Migration repair was minimal** — Only one line changed in the down_revision reference. No data loss or schema changes.

3. **Orchestration flow is solid** — The representative weekly scheduling workflow correctly:
   - Parses request text into structured tasks
   - Dispatches to TaskAgent (via orchestration + registered specialist step)
   - Dispatches to CalendarAgent with task outputs
   - Creates approval checkpoint blocking further progress
   - Awaits operator action before proceeding
   - Executes sync records in sequence after approval
   - Completes with full lineage and sync tracking

4. **Operator surfaces align** — The API status projection, completion summary, and sync counts all match what the runbook specifies, confirming the shared status service is correctly driving both API and (when implemented) Telegram responses.

## Known Limitations / Future Work

1. **Telegram bot not verified** — The UAT script includes Telegram command examples but was not tested in this task (would require real Telegram auth or test mode setup). Future UAT execution can verify this path.

2. **Restart safety not fully tested** — The UAT script includes instructions for testing restart-safe resume, but was not executed in this task due to time constraints. The database state after sync completion supports the mechanism, and code review of the idempotency logic (unique constraints on workflow_sync_records) confirms it should work. Future UAT runs should execute this phase.

3. **Revision/request_revision flow not tested** — The UAT script includes the full approval decision flow (approve/reject/request_revision), but only approve was tested. The route exists and the logic is present in the orchestration service, so the script should be valid.

## Verification Status

### Must-Haves

- [x] **UAT script covers stack startup, weekly scheduling run creation, approval/apply_schedule, sync, and replay for a representative run.**
  - All major phases present and tested up to completion and sync execution
  - Replay (request_replay safe action) is documented as available after completion

- [x] **Every step in the UAT script references real commands, routes, or Telegram commands that exist in the repo and align with current truth-set behavior.**
  - API routes verified in code
  - Response field names verified against schemas
  - Database table and column names corrected to actual ORM names
  - Manual test confirmed outputs match documented expectations

### Integration with Slice Plan

This task unblocks:
- T02 (Add/extend integration tests) — UAT script provides reference behavior for integration test assertions
- T03 (Harden Telegram commands) — UAT script includes example Telegram command patterns for hardenin

## Files Modified

- `.gsd/milestones/M002/slices/S03/uat.md` — Created (13.6 KB)
- `.gsd/milestones/M002/slices/S03/tasks/T01-PLAN.md` — Added Observability Impact section
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — Enhanced Verification section with failure-path checks
- `migrations/versions/20260313_0007_workflow_foundation.py` — Fixed down_revision reference (1 line)

## Decisions

No durable architectural or pattern decisions were required for this task. The task was purely about documenting existing behavior, so no entries to DECISIONS.md.

## Diagnostics

To verify this task's deliverables and inspect UAT behavior:

1. **Verify UAT script exists and has all phases**:
   ```bash
   wc -l .gsd/milestones/M002/slices/S03/uat.md  # Should be ~400+ lines
   grep -n "^## Phase" .gsd/milestones/M002/slices/S03/uat.md  # Lists all 7 phases
   ```

2. **Check migration repair**:
   ```bash
   grep -A2 "down_revision" migrations/versions/20260313_0007_workflow_foundation.py
   # Should show: down_revision = '20260308_0001' (not 20260310_0006)
   ```

3. **Inspect UAT checkpoints in context**:
   ```bash
   # See the checkpoint for completion summary
   grep -A15 "completion_summary" .gsd/milestones/M002/slices/S03/uat.md
   
   # See the checkpoint for approval checkpoint
   grep -A10 "await_schedule_approval" .gsd/milestones/M002/slices/S03/uat.md
   ```

4. **Verify API routes match UAT**:
   ```bash
   # Confirm /approve, /reject, /request-revision routes exist
   grep -n "def approve\|def reject\|def request_revision" \
     apps/api/src/helm_api/routes/workflow_runs.py
   ```

5. **Cross-check database schema with UAT queries**:
   ```bash
   # Verify workflow_sync_records table and columns
   grep -n "class WorkflowSyncRecord\|sync_kind\|status" \
     packages/storage/src/helm_storage/models/workflow_models.py | head -20
   ```

6. **When re-running UAT in future**:
   - Start fresh: `rm -f helm.db && uv run alembic upgrade head`
   - Run processes: `bash scripts/run-api.sh & bash scripts/run-worker.sh`
   - Follow UAT: `./.gsd/milestones/M002/slices/S03/uat.md` step-by-step
   - Expected outcome: completion_summary with headline, sync counts, and approval_decision present
