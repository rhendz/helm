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
