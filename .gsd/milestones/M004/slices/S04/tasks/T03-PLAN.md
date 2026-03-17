---
estimated_steps: 6
estimated_files: 4
---

# T03: Wire proactive notification into worker and register both new commands

**Slice:** S04 — Telegram UX Overhaul and Proactive Notifications
**Milestone:** M004

## Description

This task closes the last two deliverables of S04:

1. **Worker proactive notification**: extend `workflow_runs.run()` so that after `resume_service.resume_runnable_runs()` returns a list of resumed run IDs, any run that now has `needs_action=True` fires `TelegramDigestDeliveryService().notify_approval_needed(run_id, proposal_summary)`. This is the fix for R108 — the weekly workflow currently advances to `awaiting_approval` with no notification.

2. **Command registration**: add `CommandHandler("status", status.handle)` and `CommandHandler("agenda", agenda.handle)` to `main.py`, plus their imports.

3. **Unit tests**: `tests/unit/test_worker_notification.py` covering the notification dispatch path.

**Key constraints:**
- `TelegramDigestDeliveryService` is imported from `helm_telegram_bot.services.digest_delivery`. In the worker context this import is safe — the worker already requires `OPERATOR_TIMEZONE` and `TELEGRAM_BOT_TOKEN` as configured env vars.
- `notify_approval_needed` calls `self.deliver()` which uses `asyncio.run()` internally — this is safe in the worker's synchronous `run()` function since the worker has no running event loop.
- Do NOT call `notify_approval_needed` from any async PTB handler context — only from the synchronous worker `run()` function.
- If `notify_approval_needed` raises (e.g., missing bot token in a dev environment), catch the exception and log a warning — do not let a notification failure crash the worker job.
- Deduplication is not needed for V1: if two runs advance to `needs_action=True` in one poll cycle, both get notifications.

## Steps

1. **Extend `workflow_runs.run()` with post-resume notification**
   - File: `apps/worker/src/helm_worker/jobs/workflow_runs.py`
   - `resume_runnable_runs()` returns `list[WorkflowRunState]` — use this directly rather than re-querying via `helm_api.WorkflowStatusService` (keep the worker free of `helm_api` dependency)
   - After `resumed = resume_service.resume_runnable_runs()`, add a notification loop:
     ```python
     # Fire proactive notifications for any run that reached needs_action=True
     for state in resumed:
         if not state.run.needs_action:
             continue
         try:
             proposal_summary = ""
             schedule_proposal = state.latest_artifacts.get(
                 WorkflowArtifactType.SCHEDULE_PROPOSAL.value
             )
             if schedule_proposal is not None:
                 proposal_summary = schedule_proposal.payload.get("proposal_summary") or ""
             TelegramDigestDeliveryService().notify_approval_needed(
                 state.run.id, proposal_summary
             )
             logger.info(
                 "proactive_approval_notification_sent",
                 run_id=state.run.id,
                 workflow_type=state.run.workflow_type,
             )
         except Exception:
             logger.warning(
                 "proactive_approval_notification_failed",
                 run_id=state.run.id,
                 exc_info=True,
             )
     ```
   - Also update the return value: `return len(resumed)` → `resumed` is now `list[WorkflowRunState]`, so `len(resumed)` still works
   - Add import at the top of the file alongside existing imports:
     - `from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService`
   - `WorkflowArtifactType` is already imported from `helm_storage.repositories`

2. **Register `/status` and `/agenda` in `main.py`**
   - File: `apps/telegram-bot/src/helm_telegram_bot/main.py`
   - In the import block alongside existing `from helm_telegram_bot.commands import (...)`, add `status` and `agenda` to the import
   - Add two handler registrations after the `task` handler line (~line 95):
     ```python
     application.add_handler(CommandHandler("status", status.handle))
     application.add_handler(CommandHandler("agenda", agenda.handle))
     ```

3. **Create `tests/unit/test_worker_notification.py`**
   - Tests for the notification dispatch logic in `workflow_runs.run()`
   - The `run()` function has external deps (DB, resume service, delivery service) — test by monkeypatching
   - Pattern: patch `workflow_runs._build_resume_service` to return a fake that returns controlled `WorkflowRunState`-like objects; patch `workflow_runs.TelegramDigestDeliveryService` to capture `notify_approval_needed` calls
   - Use lightweight fake state objects with `.run.needs_action`, `.run.id`, `.run.workflow_type`, and `.latest_artifacts` fields
   - Patch `workflow_runs._build_specialist_steps` to return `{}` (no-op handlers) to simplify setup
   - Test 1: `test_notification_fired_for_needs_action_run` — resumed=[fake_state with `run.needs_action=True`, `run.id=7`, `latest_artifacts={"schedule_proposal": fake_artifact_with_proposal_summary="Schedule: dentist"}`] → `notify_approval_needed(7, "Schedule: dentist")` called once
   - Test 2: `test_no_notification_when_needs_action_false` — resumed=[fake_state with `run.needs_action=False`] → `notify_approval_needed` never called
   - Test 3: `test_no_notification_when_no_resumed_runs` — resumed=[] → `notify_approval_needed` never called
   - Test 4: `test_notification_failure_does_not_crash_worker` — resumed=[fake_state with `run.needs_action=True`], but `TelegramDigestDeliveryService().notify_approval_needed` raises `RuntimeError("no token")` → `run()` still returns without raising

4. **Verify no import regression from `TelegramDigestDeliveryService` in worker**
   - Confirm `TelegramDigestDeliveryService` can be imported in the worker context:
     ```bash
     OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c \
       "from helm_worker.jobs.workflow_runs import run; print('import ok')"
     ```
   - If this fails, check that `helm_telegram_bot.services.digest_delivery` does NOT trigger `WorkerSettings()` or any problematic eager initialization on import

5. **Run full suite to confirm no regressions**
   - `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py`

## Must-Haves

- [ ] `workflow_runs.run()` calls `notify_approval_needed` for each run in `resumed` where `needs_action=True`
- [ ] Notification failure (any exception) is caught with a warning log — worker job does not crash
- [ ] `CommandHandler("status", status.handle)` and `CommandHandler("agenda", agenda.handle)` registered in `main.py`
- [ ] `status` and `agenda` imported in `main.py` imports block
- [ ] 4 unit tests in `test_worker_notification.py`, all passing
- [ ] Full test suite passes without regressions (485+ passed)

## Verification

```bash
# Import check — confirms worker can import the delivery service
OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c \
  "from helm_worker.jobs.workflow_runs import run; print('worker import ok')"

# Handler registration check
grep -n "status.handle\|agenda.handle" apps/telegram-bot/src/helm_telegram_bot/main.py
# → must show both lines

# Worker notification tests
OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest \
  tests/unit/test_worker_notification.py -v
# → 4 passed

# Full regression check
OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest \
  tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py
# → 485+ passed, no failures
```

## Observability Impact

- Signals added/changed:
  - `proactive_approval_notification_sent` INFO log in `workflow_runs.run()` (run_id, workflow_type) — second signal for this event (first is in `notify_approval_needed` itself); both are useful for correlating worker dispatch with delivery
  - `proactive_approval_notification_failed` WARNING log in `workflow_runs.run()` when notification raises — future agent can grep this to detect silent notification failures
- How a future agent inspects this: `grep "proactive_approval_notification" <log-stream>` — both INFO (sent) and WARNING (failed) events visible; run_id links back to DB state
- Failure state exposed: if `TelegramDigestDeliveryService()` raises (bad token, network error), `proactive_approval_notification_failed` WARNING is logged with `exc_info=True` — full traceback available in logs without crashing the worker

## Inputs

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `run()` function (line ~53): `resumed = resume_service.resume_runnable_runs()` returns `list[WorkflowRunState]`. Each state has `.run.needs_action` (bool), `.run.id` (int), `.run.workflow_type` (str), `.latest_artifacts` (dict keyed by artifact type string). `WorkflowArtifactType.SCHEDULE_PROPOSAL.value` is the key for schedule proposals — already imported from `helm_storage.repositories`.
- T01 output: `TelegramDigestDeliveryService.notify_approval_needed(run_id, proposal_summary)` method must exist before this task runs (T01 adds it).
- `apps/telegram-bot/src/helm_telegram_bot/main.py` — current last registered command is at line ~95 (`task`). Import block is at lines 4–48. Both `status` and `agenda` need entries in both places.
- S04-RESEARCH.md constraint: `asyncio.run()` inside `deliver()` is safe from synchronous worker context — do NOT call from any async PTB handler.
- `packages/storage/src/helm_storage/repositories/contracts.py` — `WorkflowRunState` dataclass: `run: WorkflowRunORM`, `latest_artifacts: dict[str, WorkflowArtifactORM]`, `active_approval_checkpoint: WorkflowApprovalCheckpointORM | None`. Artifact payload is at `.payload` (dict).

## Expected Output

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `run()` extended with post-resume notification loop; `TelegramDigestDeliveryService` imported
- `apps/telegram-bot/src/helm_telegram_bot/main.py` — `status` and `agenda` imported and registered as `CommandHandler`
- `tests/unit/test_worker_notification.py` — new file with 4 passing unit tests
