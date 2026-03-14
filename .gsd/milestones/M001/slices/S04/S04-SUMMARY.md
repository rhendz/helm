# S04: Representative Scheduling Workflow

**Implemented the real representative weekly scheduling workflow proving the full kernel lifecycle from request through approved writes and replay-aware final lineage.**

## What Happened

S04 replaced demo stubs with a real weekly scheduling flow exercising the entire kernel. T01 added a shared weekly scheduling request contract with deterministic task normalization and schedule proposal generation, including carry-forward tracking, constraints, assumptions, and revision-aware regeneration. T02 completed the flow by auto-persisting final summary artifacts with approval and sync lineage, adding shared completion and recovery summaries, and verifying the full create→revision→approval→sync→completion path. T03 closed a diagnosed gap where completed-then-replayed runs showed stale success instead of replay-requested recovery, by fixing shared status precedence and adding regression coverage.

## Key Outcomes

- Shared weekly-request contract parsed identically across API and Telegram.
- Deterministic task normalization with warnings and assumptions for incomplete input.
- Rich schedule proposals with honored constraints, assumptions, carry-forward tasks, and rationale.
- Auto-persisted final summary artifacts with approval decision and sync record lineage.
- Compact completion summaries foregrounding scheduled outcome and carry-forward attention.
- Replay-aware recovery overrides stale final-summary success in live status.
- Telegram stays a thin formatter over the shared status projection.

## Verification

- `test_workflow_orchestration_service.py`: end-to-end representative worker and revision coverage, persisted approval and sync lineage in final summaries.
- `test_workflow_status_service.py`: shared create/status projection, completion/recovery summaries, completed-then-replayed regression.
- `test_telegram_commands.py`: proposal formatting, compact completion formatting, replay-requested representative runs.
- `test_workflow_status_routes.py`: API create route, proposal/revision, completed final-summary lineage.
- `test_replay_service.py`: replay lineage for completed representative runs.

## Tasks

- T01 (1h 55m): Shared request contract, deterministic normalization, proposal generation, approval flow.
- T02 (55 min): Final summary lineage, completion summaries, end-to-end verification.
- T03 (23 min): Replay-aware completion projection fix and regression coverage.
