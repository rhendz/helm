# package: orchestration

Purpose: coordinate multi-step agent workflows with explicit state transitions.

Boundaries:

- Define graph/state-machine behavior.
- Keep orchestration separate from connector and transport concerns.
- Agent-core logic should live in agent packages; Helm orchestration modules may wrap those cores for compatibility.

Recovery notes:

- Validation-failed steps persist a `validation_result` artifact, move the step to `validation_failed`, and move the run to `blocked` with `needs_action=true`.
- Blocked runs stay out of the worker runnable query until an explicit retry action creates a new pending attempt for the failed step.
- Ordinary execution failures persist the failed step, error summary, failure class, and retryability on the run and step without being collapsed into blocked validation semantics.
- Terminating a run closes it durably and prevents downstream advancement from the failed or blocked boundary.
- The `workflow_runs` worker job only resumes persisted runnable runs when step handlers are registered for the current workflow boundary.

Manual verification:

- Create a workflow run, complete a step with an invalid normalized-task artifact, and confirm the run is `blocked` with a persisted validation artifact and no downstream step advancement.
- Retry the blocked run and confirm a new pending attempt is created for the same step before the worker picks it up again.
- Simulate a step handler exception and confirm the run becomes `failed` with persisted error summary and retryability.
- Terminate a blocked or failed run and confirm the run status is `terminated` and no additional steps are queued.
