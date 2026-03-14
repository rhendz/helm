# T05: 03-adapter-writes-and-recovery-guarantees 05

**Slice:** S03 — **Milestone:** M001

## Description

Wire operator-safe replay and recovery entrypoints on top of the shared Phase 03 status and kernel semantics.

Purpose: Make deliberate replay and recovery controls reachable through API, worker, and Telegram entrypoints without duplicating the durable recovery rules established earlier in the phase.
Output: API replay endpoints, replay service wiring, worker replay job integration, Telegram recovery commands, and tests proving operator-triggered replay is reachable end-to-end.

## Must-Haves

- [ ] "Replay remains a deliberate operator action exposed through explicit API and Telegram entrypoints, never a generic retry button."
- [ ] "API, worker, and Telegram entrypoints stay thin by consuming the shared workflow status projection and kernel replay semantics from earlier plans."
- [ ] "Operator-triggered replay must be registered end-to-end so it is actually reachable from the shipped app entrypoints."

## Files

- `apps/api/src/helm_api/main.py`
- `apps/api/src/helm_api/routers/replay.py`
- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/services/replay_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/main.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/worker/src/helm_worker/jobs/replay.py`
- `tests/unit/test_replay_service.py`
- `tests/unit/test_workflow_status_service.py`
