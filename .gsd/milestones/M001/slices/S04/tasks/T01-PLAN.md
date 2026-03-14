# T01: 04-representative-scheduling-workflow 01

**Slice:** S04 — **Milestone:** M001

## Description

Implement the real representative weekly scheduling workflow on top of the existing kernel primitives.

Purpose: Replace the current demo stub with a Telegram-first, DB-first weekly planning flow that starts a `weekly_scheduling` run, normalizes a structured weekly brief into durable task artifacts, generates an honest schedule proposal, and reuses the existing approval and revision path without any dashboard-only or demo-only control plane.
Output: Shared weekly-request contract, corrected start flow, representative task and calendar specialist behavior, compact proposal read-model updates, and tests proving the fixed weekly flow reaches approval and revision safely.

## Must-Haves

- [ ] "The representative workflow starts as `weekly_scheduling` from the Telegram-first create path and persists the raw weekly brief as the durable source of truth for later steps."
- [ ] "Request parsing and representative normalization stay shared across Telegram and API create flows instead of living only inside one app-layer command handler."
- [ ] "Schedule proposals remain anchored to persisted task artifacts and still pause at the existing approval checkpoint before any task-system or calendar-system side effect runs."
- [ ] "Revision feedback regenerates a new schedule proposal version for the same run without introducing a demo-only workflow path or bypassing the shared kernel semantics."

## Files

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
