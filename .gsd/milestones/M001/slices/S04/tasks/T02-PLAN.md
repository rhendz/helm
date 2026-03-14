# T02: 04-representative-scheduling-workflow 02

**Slice:** S04 — **Milestone:** M001

## Description

Complete representative-flow lineage, completion summaries, and end-to-end verification.

Purpose: Make Phase 4 prove the kernel all the way through completion by populating a truthful final summary artifact, surfacing operator-usable completion status, and verifying representative create, revision, approval, sync, and recovery behavior across the shared API, worker, and Telegram paths.
Output: Final summary linkage populated from durable artifacts and sync rows, outcome-first completion summaries, manual verification notes, and a representative validation suite that exercises restart and revision paths.

## Must-Haves

- [ ] "A completed representative run is not done until the final summary artifact links raw request, normalized and proposal artifacts, the concrete approval decision, and downstream sync lineage."
- [ ] "Completion and recovery summaries must be built from persisted approval and sync records so restart, retry, and replay paths stay inspectable and truthful."
- [ ] "Operator-facing completion messaging remains Telegram-first and outcome-first, but detailed lineage stays available through the shared API and workflow detail surfaces."
- [ ] "Verification must prove more than a happy path by covering revision, approval gating, sync execution, and restart-safe resume during representative workflow execution."

## Files

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
