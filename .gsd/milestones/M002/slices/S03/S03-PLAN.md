# S03: Task/calendar workflow protection and verification

**Goal:** Prove that weekly scheduling / task+calendar workflows still operate end-to-end via API, worker, and Telegram after M002 cleanup, and make that verifiable via tests and a reusable UAT script.

**Demo:** From a fresh clone with Postgres running, an operator can follow `./.gsd/milestones/M002/slices/S03/uat.md` to: start API/worker/Telegram via scripts, create a weekly scheduling workflow run, approve a schedule proposal, apply the schedule, and see completion/replay summaries via API and Telegram — with pytest coverage asserting the same invariants.

## Must-Haves

- Weekly scheduling / task+calendar workflow verified end-to-end via API + worker + Telegram using a documented UAT script.
- Tests added or extended to cover the representative weekly scheduling flow and its operator-facing invariants (approval, apply_schedule, completion/replay summaries).

## Proof Level

- This slice proves: contract + integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `uv run --frozen --extra dev pytest -q tests/integration/test_weekly_scheduling_end_to_end.py tests/unit/test_workflow_telegram_commands.py` — passes all tests validating weekly scheduling end-to-end behavior and Telegram command outputs.
- `bash scripts/run-api.sh & bash scripts/run-worker.sh & bash scripts/run-telegram-bot.sh` then follow `./.gsd/milestones/M002/slices/S03/uat.md` to complete a weekly scheduling run and visually confirm expected Telegram/API outputs.
- **Failure-path inspection:** Terminate worker before approval is issued, then verify via `GET /v1/workflow-runs/{run_id}` that the run remains paused at `await_schedule_approval` with the same proposal artifact id and `available_actions` still contains `approve`. Restart worker and confirm no duplicate approvals or sync writes are created, and the run resumes cleanly. This verifies restart-safe semantics are preserved after M002 cleanup.

## Observability / Diagnostics

- Runtime signals: existing workflow run/step/artifact/sync tables, workflow status projection logs, and Telegram command outputs; extend only if a gap appears during test/UAT design.
- Inspection surfaces: workflow status API routes, `workflow_status_service` projections, Telegram `/workflows` and related commands, and database rows for a representative weekly scheduling run.
- Failure visibility: pytest failures on new end-to-end tests, mismatches between UAT expectations and actual Telegram/API outputs, and any discrepancies between projected completion summaries and persisted sync records.
- Redaction constraints: no secrets or user-identifying data logged; UAT script must avoid embedding real-world identifiers.

## Integration Closure

- Upstream surfaces consumed: `apps/api/src/helm_api/services/workflow_status_service.py`, `packages/orchestration/src/helm_orchestration/workflow_service.py`, `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`, existing workflow run routes and worker jobs, and `docs/runbooks/workflow-runs.md`.
- New wiring introduced in this slice: explicit integration tests that drive weekly scheduling through API and Telegram, plus a `uat.md` script that threads API, worker, and Telegram surfaces together for an operator.
- What remains before the milestone is truly usable end-to-end: nothing beyond executing this slice’s tests and UAT; future milestones may add additional workflows, but weekly scheduling will be covered.

## Tasks

- [x] **T01: Define UAT script for weekly scheduling flow** `est:45m`
  - Why: Capture a single, operator-focused walkthrough that proves weekly scheduling works via API/worker/Telegram and can be rerun after future cleanup.
  - Files: `./.gsd/milestones/M002/slices/S03/uat.md`, `docs/runbooks/workflow-runs.md`
  - Do: Draft `uat.md` that builds on the existing workflow-runs runbook but narrows to weekly scheduling: stack startup commands, creating a representative weekly scheduling run, inspecting schedule proposals, performing approval/revision/reject flows, applying the schedule, and verifying completion/replay summaries through API and Telegram. Ensure steps are precise and reference actual scripts and routes.
  - Verify: Manually walk through `uat.md` once to ensure every command and path is valid and results match expectations at each stage.
  - Done when: A future operator can follow `uat.md` from a fresh environment and complete a weekly scheduling run without guesswork.
- [x] **T02: Add/extend integration test for weekly scheduling end-to-end** `est:1h`
  - Why: Provide automated coverage that the representative weekly scheduling flow works through API + worker semantics and matches the projections/operators rely on.
  - Files: `tests/integration/test_weekly_scheduling_end_to_end.py`, `apps/api/src/helm_api/services/workflow_status_service.py`, `apps/worker/src/helm_worker/jobs/workflow_runs.py`
  - Do: Implement or extend an integration test that drives creation of a weekly scheduling run via API, simulates worker progression through schedule proposal, approval, apply_schedule, and sync, then asserts on key invariants (approval checkpoint behavior, proposal and sync linkage, completion summary fields). Reuse existing helpers/fixtures; avoid introducing new workflow types.
  - Verify: `uv run --frozen --extra dev pytest -q tests/integration/test_weekly_scheduling_end_to_end.py`
  - Done when: The integration test passes and fails meaningfully if weekly scheduling behavior or projections regress.
- [x] **T03: Harden Telegram workflow commands around completion and replay** `est:1h`
  - Why: Ensure Telegram remains a reliable operator surface for weekly scheduling completion and replay, aligned with the shared workflow status projection and new tests/UAT.
  - Files: `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`, `tests/unit/test_workflow_telegram_commands.py`, `apps/api/src/helm_api/services/workflow_status_service.py`
  - Do: Review existing Telegram workflow commands and status formatting for weekly scheduling runs; add or tighten unit tests to assert on completion headlines, replay messaging, and safe_next_actions for representative cases. Adjust formatting only where needed to align with the shared completion summary and avoid brittle string expectations.
  - Verify: `uv run --frozen --extra dev pytest -q tests/unit/test_workflow_telegram_commands.py`
  - Done when: Telegram tests clearly protect weekly scheduling completion/replay semantics and remain aligned with API status projections and the UAT script.

## Files Likely Touched

- `./.gsd/milestones/M002/slices/S03/uat.md`
- `tests/integration/test_weekly_scheduling_end_to_end.py`
- `tests/unit/test_workflow_telegram_commands.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `docs/runbooks/workflow-runs.md`