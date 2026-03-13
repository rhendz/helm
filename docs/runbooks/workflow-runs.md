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
- Retry a blocked validation failure or retryable failed run:
  `POST /v1/workflow-runs/{run_id}/retry` with `{"reason":"..."}`.
- Terminate a blocked or failed run:
  `POST /v1/workflow-runs/{run_id}/terminate` with `{"reason":"..."}`.

Expected operator signals:

- `paused_state` is explicit for blocked validation failures and ordinary failed runs.
- `pause_reason` stays nullable and carries the validation or failure summary when the run is paused.
- `available_actions` shows whether retry and terminate are valid next steps.
- `lineage.final_summary` always includes nullable approval and downstream sync linkage fields.

## Telegram Checks

- Start a run:
  `/workflow_start Plan my week around deep work`
- List recent runs:
  `/workflows`
- List only runs needing operator attention:
  `/workflow_needs_action`
- Retry a run:
  `/workflow_retry <run_id> Operator requested retry after correction.`
- Terminate a run:
  `/workflow_terminate <run_id> Operator terminated failed run.`

Expected Telegram output:

- Each response shows run ID, current status, current step, explicit paused state, last outcome, whether action is needed, and the next recovery actions.
- Blocked validation failures remain distinct from ordinary execution failures because the summary keeps `paused_state` and `failure_kind` explicit.
