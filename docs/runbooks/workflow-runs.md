# Workflow Runs

## API Checks

- Create a run:
  `POST /v1/workflow-runs` with `workflow_type`, `first_step_name`, `request_text`, `submitted_by`, `channel`, and `metadata`.
- Verify the response includes `id`, `status`, and `current_step`.
- Inspect recent runs:
  `GET /v1/workflow-runs`
- Inspect runs needing action:
  `GET /v1/workflow-runs?needs_action=true`
- Inspect a single run with lineage:
  `GET /v1/workflow-runs/{run_id}`
- Inspect schedule proposal versions for a run:
  `GET /v1/workflow-runs/{run_id}/proposal-versions`
- Retry a blocked validation failure or retryable failed run:
  `POST /v1/workflow-runs/{run_id}/retry` with `{"reason":"..."}`.
- Terminate a blocked or failed run:
  `POST /v1/workflow-runs/{run_id}/terminate` with `{"reason":"..."}`.
- Approve, reject, or request revision for a specific proposal artifact:
  `POST /v1/workflow-runs/{run_id}/approve`
  `POST /v1/workflow-runs/{run_id}/reject`
  `POST /v1/workflow-runs/{run_id}/request-revision`
  Include `{"actor":"...","target_artifact_id":<proposal_artifact_id>}` and add `feedback` for revision requests.

Expected operator signals:

- `paused_state` is explicit for blocked validation failures and ordinary failed runs.
- `pause_reason` stays nullable and carries the validation or failure summary when the run is paused.
- `available_actions` shows whether retry and terminate are valid next steps.
- `lineage.final_summary` always includes nullable approval and downstream sync linkage fields.
- `proposal_versions` is returned latest-first, keeps superseded versions inspectable, and shows which concrete artifact was approved or rejected.

## Telegram Checks

- Start a run:
  `/workflow_start Plan my week around deep work`
- List recent runs:
  `/workflows`
- List only runs needing operator attention:
  `/workflow_needs_action`
- Inspect prior proposal versions for one run:
  `/workflow_versions <run_id>`
- Retry a run:
  `/workflow_retry <run_id> Operator requested retry after correction.`
- Terminate a run:
  `/workflow_terminate <run_id> Operator terminated failed run.`
- Approve or reject the current proposal version:
  `/approve <run_id> <proposal_artifact_id>`
  `/reject <run_id> <proposal_artifact_id>`
- Request a revision with explicit feedback:
  `/request_revision <run_id> <proposal_artifact_id> Keep Friday afternoon open.`

Expected Telegram output:

- Each response shows run ID, current status, current step, explicit paused state, last outcome, whether action is needed, and the next recovery actions.
- Blocked validation failures remain distinct from ordinary execution failures because the summary keeps `paused_state` and `failure_kind` explicit.
- Approval-blocked runs show the latest proposal version and artifact ID so operators can target the correct version explicitly.
- `/workflow_versions` lists older schedule proposal versions, including whether each one is current, superseded, approved, or rejected.

## Manual Revision Verification

1. Start or seed a scheduling workflow until it blocks on `await_schedule_approval`.
2. Inspect `GET /v1/workflow-runs/{run_id}` or `/workflow_needs_action` and note the latest `target_artifact_id` and version number.
3. Request revision against that artifact with feedback.
4. Confirm the run returns to `dispatch_calendar_agent` and then blocks again on a new approval checkpoint.
5. Verify `GET /v1/workflow-runs/{run_id}/proposal-versions` returns a new latest version, while the older version remains present and marked superseded.
6. Verify the superseded version exposes the revision feedback summary that triggered the rework.
7. Approve the new version by posting the new `target_artifact_id`.
8. Confirm run detail shows the approved decision attached to the approved proposal artifact, while the older version remains inspectable but not actionable.

## Representative Weekly Scheduling Verification

Use one realistic weekly brief for both Telegram and API checks so the persisted request contract matches:

- `Plan my week. Tasks: Finish roadmap draft high due Wednesday 90m; Prep interviews medium 120m; Clear inbox low 30m. Constraints: protect deep work mornings; keep Friday afternoon open.`

### Telegram create and proposal review

1. Start the run with `/workflow_start <brief>`.
2. Confirm the reply shows `workflow_type=weekly_scheduling`, `step=dispatch_task_agent`, and the parsed request stays compact instead of echoing every raw section.
3. Resume the worker until the run blocks on approval.
4. Check `/workflow_needs_action` and confirm the proposal output is outcome-first:
   - scheduled block preview is visible
   - honored constraints and assumptions are visible when present
   - carry-forward work is visible when not everything fits
   - the actionable proposal artifact id is visible for approve/reject/revision

### Revision and version history

1. Request a revision with `/request_revision <run_id> <proposal_artifact_id> Keep Friday afternoon open and move interview prep earlier.`
2. Confirm the run resumes at `dispatch_calendar_agent`, then returns to `await_schedule_approval`.
3. Run `/workflow_versions <run_id>` and confirm:
   - the newest version is first
   - the prior version is marked `superseded`
   - the superseded version retains the revision feedback summary

### Approval, completion, and lineage

1. Approve the current proposal with `/approve <run_id> <proposal_artifact_id>` or `POST /v1/workflow-runs/{run_id}/approve`.
2. Confirm no downstream task or calendar write exists before approval, and that sync rows are created immediately after approval.
3. Let `apply_schedule` finish, then inspect `GET /v1/workflow-runs/{run_id}`.
4. Confirm the completed response includes:
   - `completion_summary.headline` describing scheduled outcome and approved-write count
   - `completion_summary.carry_forward_tasks` for work that did not fit
   - `lineage.final_summary.approval_decision=approve`
   - `lineage.final_summary.approval_decision_artifact_id`
   - `lineage.final_summary.downstream_sync_status=succeeded`
   - `lineage.final_summary.downstream_sync_reference_ids` for both task and calendar writes

### Restart-safe resume around approval and apply_schedule

1. Stop the worker after the proposal is created and approval is pending.
2. Restart the worker and confirm the run still waits at `await_schedule_approval` with the same actionable artifact id.
3. Approve the proposal, then stop the worker after one sync row succeeds but before all writes finish.
4. Restart the worker and confirm it resumes only the remaining sync work instead of repeating already-succeeded writes.
5. Re-check `GET /v1/workflow-runs/{run_id}` and confirm the final summary lineage still points at the approved proposal version and the persisted sync records from the resumed execution.
