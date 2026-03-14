# UAT Script: Weekly Scheduling Workflow

**Goal:** Verify that the weekly scheduling workflow operates end-to-end via API, worker, and Telegram after M002 cleanup.

**Duration:** ~15–20 minutes of active work.

**Prerequisites:**
- Postgres running with Helm schema initialized (`bash scripts/migrate.sh`)
- Three terminal windows or tmux panes ready for API, worker, and Telegram processes
- `httpie` or `curl` available for API calls (examples use httpie; curl equivalents noted below)
- Basic familiarity with the runbook in `docs/runbooks/workflow-runs.md`

---

## Phase 1: Environment Setup

### 1.1 Initialize Database

```bash
bash scripts/migrate.sh
```

Expected output: Alembic upgrades to latest revision with no errors. Confirm:
- `workflow_runs` table exists
- `workflow_steps`, `workflow_artifacts`, `workflow_approval_checkpoints`, `workflow_sync_records` tables exist

Quick check:
```bash
sqlite3 helm.db "SELECT COUNT(*) FROM workflow_runs;"
```

Expected: `0` (fresh state).

### 1.2 Start Services in Parallel

**Terminal 1 — API:**
```bash
bash scripts/run-api.sh
```

Expected: Server listens on `http://localhost:8000`, logs show `Uvicorn running on 0.0.0.0:8000`.

**Terminal 2 — Worker:**
```bash
bash scripts/run-worker.sh
```

Expected: Worker starts, logs show readiness polling and waiting for jobs.

**Terminal 3 — Telegram Bot:**
```bash
bash scripts/run-telegram-bot.sh
```

Expected: Telegram bot starts, logs show connection established (or test mode ready if no real Telegram token).

---

## Phase 2: Create Weekly Scheduling Run

### 2.1 Via API

Create a representative weekly scheduling workflow run:

```bash
http POST http://localhost:8000/v1/workflow-runs \
  workflow_type=weekly_scheduling \
  first_step_name=dispatch_task_agent \
  request_text="Plan my week. Tasks: Finish roadmap draft high due Wednesday 90m; Prep interviews medium 120m; Clear inbox low 30m. Constraints: protect deep work mornings; keep Friday afternoon open." \
  submitted_by="test-operator" \
  channel="api"
```

**Curl equivalent:**
```bash
curl -X POST http://localhost:8000/v1/workflow-runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "weekly_scheduling",
    "first_step_name": "dispatch_task_agent",
    "request_text": "Plan my week. Tasks: Finish roadmap draft high due Wednesday 90m; Prep interviews medium 120m; Clear inbox low 30m. Constraints: protect deep work mornings; keep Friday afternoon open.",
    "submitted_by": "test-operator",
    "channel": "api"
  }'
```

Expected response:
```json
{
  "id": 1,
  "workflow_type": "weekly_scheduling",
  "status": "active",
  "current_step": "dispatch_task_agent",
  "submitted_by": "test-operator",
  "channel": "api",
  "needs_action": false
}
```

**Checkpoint:** Note the `id` (e.g., `1`). Use this throughout the UAT.

### 2.2 Verify Run Created

```bash
http GET http://localhost:8000/v1/workflow-runs
```

Expected: List includes the newly created run with `status=active` and `current_step=dispatch_task_agent`.

---

## Phase 3: Proposal Generation and Approval

### 3.1 Let Worker Progress to Approval Checkpoint

Allow the worker to run and advance the workflow. Monitor the worker logs:

Expected sequence in worker logs:
1. `dispatch_task_agent` begins, parsing the request
2. TaskAgent invoked with structured task specifications
3. TaskAgent returns task representations
4. `dispatch_calendar_agent` begins
5. CalendarAgent invoked with tasks and constraints
6. CalendarAgent returns schedule proposal
7. Workflow blocks at `await_schedule_approval`

This typically takes **2–5 seconds**.

### 3.2 Inspect Run Detail at Approval Checkpoint

```bash
http GET http://localhost:8000/v1/workflow-runs/1
```

Expected response fields:
- `status`: `active`
- `paused_state`: `awaiting_approval`
- `current_step`: `await_schedule_approval`
- `approval_checkpoint` (object):
  - `target_artifact_id`: (integer, e.g., `3`)
  - `target_version_number`: `1`
  - `proposal_summary`: (string describing the schedule)
- `needs_action`: `true`
- `available_actions`: array containing `{"action": "approve"}`, `{"action": "reject"}`, `{"action": "request_revision"}`

**Checkpoint:** Note the `approval_checkpoint.target_artifact_id` (e.g., `3`) and version (`1`). You will use these in the next step.

### 3.3 Inspect Proposal Details

```bash
http GET http://localhost:8000/v1/workflow-runs/1/proposal-versions
```

Expected response: Array with one version object:
```json
{
  "artifact_id": 3,
  "version_number": 1,
  "current": true,
  "approved": false,
  "rejected": false,
  "superseded": false,
  "proposal_summary": "...",
  "time_blocks": [...],
  "honored_constraints": [...],
  "carry_forward_tasks": [...]
}
```

Verify:
- `current`: `true`
- `time_blocks` contains scheduled work items
- `honored_constraints` lists constraints from the request (e.g., "protect deep work mornings")
- `carry_forward_tasks` is empty or contains work that didn't fit

---

## Phase 4: Approval Decision and Execution

### 4.1 Approve the Proposal

Using the artifact ID from the checkpoint (e.g., `3`):

```bash
http POST http://localhost:8000/v1/workflow-runs/1/approve \
  actor=test-operator \
  target_artifact_id=3
```

**Curl equivalent:**
```bash
curl -X POST http://localhost:8000/v1/workflow-runs/1/approve \
  -H "Content-Type: application/json" \
  -d '{"actor": "test-operator", "target_artifact_id": 3}'
```

Expected response:
```json
{
  "id": 1,
  "status": "active",
  "paused_state": null,
  "current_step": "apply_schedule"
}
```

**Checkpoint:** The run is no longer paused and has moved to `apply_schedule`.

### 4.2 Allow Worker to Complete Apply Schedule

Monitor the worker logs:

Expected sequence:
1. `apply_schedule` begins
2. Adapter-gated sync executes, creating sync records for task writes
3. Adapter-gated sync executes, creating sync records for calendar writes
4. All sync rows complete with `status=succeeded`
5. Workflow advances to completion
6. Completion summary is generated with `headline`, `total_sync_writes`, `downstream_sync_status=succeeded`

This typically takes **2–5 seconds**.

### 4.3 Inspect Completed Run

```bash
http GET http://localhost:8000/v1/workflow-runs/1
```

Expected response fields:
- `status`: `completed`
- `paused_state`: `null`
- `current_step`: (no active step)
- `completion_summary` (object):
  - `headline`: (string describing outcome, e.g., "Weekly schedule applied: 3 tasks, 2 calendar blocks")
  - `scheduled_highlights`: (array of scheduled item summaries)
  - `carry_forward_tasks`: (array of tasks not scheduled, if any)
  - `total_sync_writes`: (integer >= 2, e.g., `5`)
  - `task_sync_writes`: (integer, e.g., `3`)
  - `calendar_sync_writes`: (integer, e.g., `2`)
  - `downstream_sync_status`: `succeeded`
- `lineage.final_summary` (object):
  - `approval_decision`: `approve`
  - `approval_decision_actor`: `test-operator`
  - `approval_decision_artifact_id`: `3` (the approved proposal)
  - `downstream_sync_status`: `succeeded`
  - `downstream_sync_reference_ids`: (array of sync record IDs)
- `needs_action`: `false`

**Checkpoint:** The workflow completed successfully with clear linkage between approval decision and sync execution.

---

## Phase 5: Verify Sync Records and Database State

### 5.1 Inspect Sync Records

List all sync records for this run:

```bash
sqlite3 helm.db "SELECT id, run_id, step_id, target_system, sync_kind, status FROM workflow_sync_records WHERE run_id = 1 ORDER BY id;"
```

Expected output (example):
```
1|1|4|task|write|succeeded
2|1|4|task|write|succeeded
3|1|4|task|write|succeeded
4|1|5|calendar|write|succeeded
5|1|5|calendar|write|succeeded
```

Verify:
- At least 2 sync records per run (task and calendar writes)
- All have `status=succeeded`
- `run_id` matches the workflow run ID
- `target_system` includes both `task` and `calendar`

### 5.2 Verify Approval Checkpoint Persistence

```bash
sqlite3 helm.db "SELECT run_id, id, target_artifact_id, decision FROM workflow_approval_checkpoints WHERE run_id = 1;"
```

Expected output (example):
```
1|1|3|approve
```

Verify:
- One approval checkpoint per run (for this workflow type)
- `decision=approve` matches the decision made
- `target_artifact_id` matches the artifact ID you approved

---

## Phase 6: Telegram Operator Surface

### 6.1 Via Telegram Commands (Test Mode or Sandbox)

If you have Telegram bot access in test/sandbox mode, verify operator commands:

```
/workflows
```

Expected Telegram response:
```
Run 1 [completed] step=n/a paused=null
Last: Schedule applied and synced.
Needs action: no | Next: none
Outcome: Weekly schedule applied: 3 tasks, 2 calendar blocks
Scheduled: [Finish roadmap draft], [Interview prep block]
Sync: 5 writes (3 task, 2 calendar) status=succeeded
Carry forward: [Clear inbox]
```

Verify:
- `status=completed`
- `paused=null` (run is not paused)
- Completion headline and sync status are visible
- Carry-forward work listed if applicable

---

## Phase 7: Restart-Safe Resume Verification

### 7.1 Create a New Run and Stop Before Completion

Create another run:

```bash
http POST http://localhost:8000/v1/workflow-runs \
  workflow_type=weekly_scheduling \
  first_step_name=dispatch_task_agent \
  request_text="Plan my week. Tasks: Big project 180m; Review code 60m. Constraints: block mornings." \
  submitted_by="test-operator" \
  channel="api"
```

Note the new run ID (e.g., `2`).

Allow the worker to reach the approval checkpoint, then **stop the worker process** (`Ctrl+C` in Terminal 2).

Verify via API that the run is still paused:

```bash
http GET http://localhost:8000/v1/workflow-runs/2
```

Expected:
- `paused_state`: `awaiting_approval`
- `current_step`: `await_schedule_approval`
- `approval_checkpoint.target_artifact_id`: (same as before stop)

### 7.2 Restart Worker and Approve

Restart the worker:

```bash
bash scripts/run-worker.sh
```

Approve the proposal with the target artifact ID from the checkpoint:

```bash
http POST http://localhost:8000/v1/workflow-runs/2/approve \
  actor=test-operator \
  target_artifact_id=<target_artifact_id_from_checkpoint>
```

### 7.3 Stop Worker Mid-Sync and Resume

Allow one or two sync records to complete, then stop the worker again.

Verify via database:

```bash
sqlite3 helm.db "SELECT COUNT(*) FROM workflow_sync_records WHERE run_id = 2 AND outcome_status = 'succeeded';"
```

Expected: 1 or 2.

Restart the worker and allow it to finish:

```bash
bash scripts/run-worker.sh
```

### 7.4 Verify Completion Without Duplication

Inspect the final run:

```bash
http GET http://localhost:8000/v1/workflow-runs/2
```

Expected:
- `status`: `completed`
- `completion_summary.total_sync_writes`: Correct total (e.g., 5, not 7 or 10)

Verify sync records:

```bash
sqlite3 helm.db "SELECT COUNT(*) FROM workflow_sync_records WHERE run_id = 2;"
```

Expected: Exact count (e.g., 5), not duplicated due to resume.

**Checkpoint:** The workflow safely resumed without re-running completed sync writes.

---

## Verification Summary

| Checkpoint | Expected State | Status |
|---|---|---|
| 1. Database initialized | `workflow_runs` count = 0 | ✓ |
| 2. Run created | API returns run with ID and `status=active` | ✓ |
| 3. Run advanced to approval | `current_step=await_schedule_approval`, `paused_state=awaiting_approval` | ✓ |
| 4. Proposal visible | `/proposal-versions` returns schedule with constraints and time blocks | ✓ |
| 5. Approval issued | Run moves to `apply_schedule`, no longer paused | ✓ |
| 6. Sync completed | `downstream_sync_status=succeeded`, 5+ sync records with `outcome_status=succeeded` | ✓ |
| 7. Run completed | `status=completed`, `completion_summary` populated with outcome and sync count | ✓ |
| 8. Telegram surfaces show completion | `/workflows` shows completed run with outcome headline and sync summary | ✓ |
| 9. Resume-safe at approval | Stopping before approval preserves checkpoint; restart resumes cleanly | ✓ |
| 10. Resume-safe during sync | Stopping mid-sync; restart does not duplicate completed writes | ✓ |

---

## Cleanup

Stop all services:

```bash
pkill -f "run-api.sh\|run-worker.sh\|run-telegram-bot.sh"
```

Or in each terminal:
```bash
Ctrl+C
```

Optional: Reset database for next test run:
```bash
rm helm.db
bash scripts/migrate.sh
```

---

## Troubleshooting

### Run Doesn't Advance to Approval

- Check worker logs for errors in `dispatch_task_agent` or `dispatch_calendar_agent`
- Verify `REQUEST_TEXT` is passed correctly
- Confirm agents are registered in the orchestration kernel

### Sync Records Not Created or Status Not Succeeded

- Check worker logs for adapter errors
- Verify mock or real external system endpoints are accessible
- Inspect `helm_workflow_sync_records` directly for `error_detail` field

### Telegram Commands Not Working

- Verify Telegram bot is running and authorized
- Check that `submitted_by` and `actor` values match expected format
- Confirm run ID and artifact ID are parsed correctly

### Resume Duplication or Loss of State

- Check database transaction isolation in worker restart logic
- Verify `workflow_sync_records` idempotency key is unique
- Inspect logs for "already completed" or "skipping" messages during resume

---

## Reference

- Runbook: `docs/runbooks/workflow-runs.md`
- Truth-set: `.gsd/milestones/M002/M002-TRUTH-NOTE.md`
- API schemas: `apps/api/src/helm_api/schemas.py`
- Workflow service: `packages/orchestration/src/helm_orchestration/workflow_service.py`
- Telegram commands: `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`, `approve.py`
