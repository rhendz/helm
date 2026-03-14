# S04: Representative Scheduling Workflow

**Goal:** Implement the real representative weekly scheduling workflow on top of the existing kernel primitives.
**Demo:** Implement the real representative weekly scheduling workflow on top of the existing kernel primitives.

## Must-Haves


## Tasks

- [x] **T01: 04-representative-scheduling-workflow 01** `est:1h 55m`
  - Implement the real representative weekly scheduling workflow on top of the existing kernel primitives.

Purpose: Replace the current demo stub with a Telegram-first, DB-first weekly planning flow that starts a `weekly_scheduling` run, normalizes a structured weekly brief into durable task artifacts, generates an honest schedule proposal, and reuses the existing approval and revision path without any dashboard-only or demo-only control plane.
Output: Shared weekly-request contract, corrected start flow, representative task and calendar specialist behavior, compact proposal read-model updates, and tests proving the fixed weekly flow reaches approval and revision safely.
- [x] **T02: 04-representative-scheduling-workflow 02** `est:55 min`
  - Complete representative-flow lineage, completion summaries, and end-to-end verification.

Purpose: Make Phase 4 prove the kernel all the way through completion by populating a truthful final summary artifact, surfacing operator-usable completion status, and verifying representative create, revision, approval, sync, and recovery behavior across the shared API, worker, and Telegram paths.
Output: Final summary linkage populated from durable artifacts and sync rows, outcome-first completion summaries, manual verification notes, and a representative validation suite that exercises restart and revision paths.
- [x] **T03: 04-representative-scheduling-workflow 03** `est:23 min`
  - Close the diagnosed Phase 4 replay-summary gap without replanning the representative workflow.

Purpose: Make completed-then-replayed representative runs render truthfully as replay-requested recovery work by fixing shared status precedence and adding the minimum regression coverage around replay, status projection, and Telegram summaries.
Output: One focused projection fix in the shared status service plus targeted tests that prove stale final-summary success no longer masks live replay recovery state.

## Files Likely Touched

- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/unit/test_telegram_commands.py`
- `tests/integration/test_workflow_status_routes.py`
- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `docs/runbooks/workflow-runs.md`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `tests/unit/test_replay_service.py`
- `tests/unit/test_telegram_commands.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/integration/test_workflow_status_routes.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `tests/unit/test_replay_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/unit/test_telegram_commands.py`
