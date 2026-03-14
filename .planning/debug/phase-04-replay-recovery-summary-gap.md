---
status: resolved
phase: 04-representative-scheduling-workflow
created: 2026-03-13T03:40:00Z
updated: 2026-03-13T03:40:00Z
---

# Debug Session: Phase 4 Replay Recovery Summary Gap

## Symptom

After `/workflow_replay 1 Check replay recovery summary.`, Telegram `/workflows` continued to show the run as an ordinary completed run:

- `Run 1 [completed]`
- `Outcome: Scheduled 3 block(s) and synced 6 approved write(s).`

The expected behavior was recovery-oriented follow-up messaging after replay request.

## Root Cause

The shared status projection in `apps/api/src/helm_api/services/workflow_status_service.py` prioritizes persisted successful final-summary state before live replay-requested recovery state. For representative runs that completed once and then entered replay, Telegram inherits the stale shared completion summary and renders a misleading ordinary-completed outcome.

## Affected Artifacts

- `apps/api/src/helm_api/services/workflow_status_service.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `tests/unit/test_replay_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/unit/test_telegram_commands.py`

## Missing Coverage

- Completed representative run -> replay requested -> shared summary switches to recovery/follow-up messaging.
- Telegram `/workflows` coverage for that same completed-then-replay scenario.

## Recommended Fix Shape

- Let live recovery classification override stale final-summary success in shared completion messaging.
- Surface replay follow-up in `attention_items` and downstream sync status when recovery is active.
- Add targeted tests for API/status and Telegram list output in the completed-then-replay path.
