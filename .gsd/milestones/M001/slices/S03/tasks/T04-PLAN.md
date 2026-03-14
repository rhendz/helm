# T04: 03-adapter-writes-and-recovery-guarantees 04

**Slice:** S03 — **Milestone:** M001

## Description

Expose Phase 03 recovery semantics through one shared workflow status projection.

Purpose: Make the durable sync and recovery facts from earlier Phase 03 plans legible to operators before execution and after partial success, while keeping the projection itself separate from API, worker, and Telegram entrypoint wiring.
Output: Shared workflow status projection updates and tests proving operators can inspect effect summaries, partial sync, and recovery state from one durable read model.

## Must-Haves

- [ ] "Operator surfaces present a compact pre-execution effect summary before adapter execution begins, including how many task and calendar writes approval will trigger."
- [ ] "API and Telegram surfaces consume one shared workflow status projection for sync counts, partial success, recovery class, and safe next actions."
- [ ] "The shared projection reads durable sync and recovery facts directly, so app entrypoints stay thin and consistent."

## Files

- `apps/api/src/helm_api/services/workflow_status_service.py`
- `tests/unit/test_workflow_status_service.py`
