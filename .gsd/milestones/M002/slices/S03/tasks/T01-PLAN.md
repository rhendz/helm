---
estimated_steps: 6
estimated_files: 2
---

# T01: Define UAT script for weekly scheduling flow

**Slice:** S03 — Task/calendar workflow protection and verification
**Milestone:** M002

## Description

Author a focused UAT script for the representative weekly scheduling / task+calendar workflow that an operator can run after M002 cleanup. The script should walk through starting the stack (API, worker, Telegram), creating a weekly scheduling workflow run, inspecting schedule proposals, performing approval/revision decisions, applying the schedule, and verifying completion and replay behavior via API and Telegram. It should lean on existing runbook content but present a single, concise path centered on weekly scheduling.

## Steps

1. Review `docs/runbooks/workflow-runs.md` and identify sections relevant to weekly scheduling, approval checkpoints, apply_schedule, sync, and replay.
2. Confirm current scripts and commands for starting API, worker, and Telegram (`scripts/run-api.sh`, `scripts/run-worker.sh`, `scripts/run-telegram-bot.sh`) and any required Postgres setup/migration steps.
3. Design the UAT flow as a linear sequence: environment setup, creating a weekly scheduling run (via API route or helper script), inspecting the schedule proposal, issuing approval/revision/reject via operator surface, applying the schedule, and inspecting completion/replay summaries.
4. Write `./.gsd/milestones/M002/slices/S03/uat.md` with concrete commands (curl/httpie examples, script invocations, Telegram commands) and explicit checkpoints for what the operator should see at each stage.
5. Cross-check UAT expectations against `workflow_status_service` projections and Telegram command outputs to ensure terminology and fields match reality.
6. Run through the UAT script end-to-end once (or as far as feasible in this environment), adjusting any commands, paths, or expectations that do not match actual behavior.

## Must-Haves

- [ ] UAT script covers stack startup, weekly scheduling run creation, approval/apply_schedule, sync, and replay for a representative run.
- [ ] Every step in the UAT script references real commands, routes, or Telegram commands that exist in the repo and align with current truth-set behavior.

## Verification

- `bash scripts/run-api.sh & bash scripts/run-worker.sh & bash scripts/run-telegram-bot.sh` then follow `./.gsd/milestones/M002/slices/S03/uat.md` to complete a weekly scheduling run and confirm that each checkpoint is achievable and matches observed behavior.
- Manually confirm that `uat.md` references the correct scripts, routes, and Telegram commands by grepping the repo and spot-checking outputs where possible.

## Inputs

- `docs/runbooks/workflow-runs.md` — existing workflow run runbook to mine for weekly scheduling steps and terminology.
- `.gsd/milestones/M002/M002-TRUTH-NOTE.md` — truth-set framing to keep UAT focused on weekly scheduling and task/calendar flows.

## Observability Impact

When this task completes, the following inspection surfaces become available to verify weekly scheduling workflows end-to-end:

- **UAT script artifact:** `.gsd/milestones/M002/slices/S03/uat.md` serves as the durable walkthrough for future operators to validate weekly scheduling state. Failure visibility: if any step's command/route doesn't exist or outputs don't match documented expectations, the operator will see immediate parse errors or mismatch alerts.
- **Runtime signals during UAT execution:** Workflow run tables (`workflow_runs`, `workflow_steps`, `workflow_artifacts`, `workflow_approval_checkpoints`, `workflow_sync_records`) contain persisted state that can be inspected via SQL after each UAT step. Log output from worker/API shows proposal dispatch, approval blocking, and sync progression.
- **Telegram and API operator surfaces:** `/workflows`, `/workflow_needs_action`, `GET /v1/workflow-runs?needs_action=true`, and approval endpoints show whether the run is progressing and paused at expected checkpoints. Mismatch with UAT expectations signals a failure in completion summary formatting, status projection, or approval linkage.
- **Failure diagnostics:** If UAT execution fails partway, the operator has: database row inspection to see which step was reached, `workflow_sync_records` showing which external writes succeeded/failed, and Telegram/API status output showing the last outcome and available next actions.

## Expected Output

- `./.gsd/milestones/M002/slices/S03/uat.md` — a concise, end-to-end UAT script that an operator can follow to validate weekly scheduling / task+calendar workflows via API, worker, and Telegram after cleanup.