---
estimated_steps: 7
estimated_files: 2
---

# T01: Replace _build_calendar_adapter with GoogleCalendarProvider in both execution paths

**Slice:** S03 — Unified /task Pipeline
**Milestone:** M005

## Description

Replace the bespoke `_build_calendar_adapter()` function (which constructs `GoogleCalendarAdapter` from env-var credentials or falls back to `StubCalendarSystemAdapter`) with `GoogleCalendarProvider(user_id, db)` construction in both:
1. The **worker recovery path** in `workflow_runs.py` (`_build_resume_service`)
2. The **telegram inline path** in `workflow_status_service.py` (`execute_task_run`, `execute_after_approval`)

The user lookup chain for provider construction is:
- **Telegram inline path**: Parse `submitted_by` field (format `"telegram:{telegram_user_id}"`) → `get_user_by_telegram_id(telegram_user_id, db)` → `user.id` → `GoogleCalendarProvider(user.id, db)`
- **Worker recovery path**: `os.getenv("TELEGRAM_ALLOWED_USER_ID")` → `get_user_by_telegram_id(int(telegram_user_id_str), db)` → `user.id` → `GoogleCalendarProvider(user.id, db)`

**Key constraints:**
- `WorkflowOrchestrationService.__init__` accepts `calendar_system_adapter: CalendarSystemAdapter | None` — its signature must NOT change
- `GoogleCalendarProvider` satisfies `CalendarSystemAdapter` protocol structurally (has `upsert_calendar_block` and `reconcile_calendar_block`)
- `StubTaskSystemAdapter` still imported from `helm_connectors` — only calendar adapter references are removed in this slice
- `GoogleCalendarProvider(user_id, db)` must be constructed inside the same `SessionLocal()` block where the session is active
- If user lookup fails, raise `RuntimeError` with a clear message — do NOT fall back to a stub silently
- The lazy import guard for `_build_calendar_adapter` (avoiding worker config import at module level) is no longer needed — `helm_providers` has no worker config dependency, so `GoogleCalendarProvider` can be a top-level import

**Available skill:** `lint` — use for ruff check at the end.

## Steps

1. **Edit `apps/worker/src/helm_worker/jobs/workflow_runs.py`**:
   - Remove the import line: `from helm_connectors.google_calendar import GoogleCalendarAdapter, GoogleCalendarAuth`
   - Remove `StubCalendarSystemAdapter` from the `from helm_connectors import ...` line (keep `StubTaskSystemAdapter`)
   - Add imports: `from helm_providers import GoogleCalendarProvider` and `from helm_storage.repositories.users import get_user_by_telegram_id`
   - Delete the entire `_build_calendar_adapter()` function (lines ~131–143)
   - Add a `_resolve_bootstrap_user_id(db: Session) -> int` helper function that:
     - Reads `TELEGRAM_ALLOWED_USER_ID` from env
     - Calls `get_user_by_telegram_id(int(telegram_user_id_str), db)`
     - Raises `RuntimeError("Bootstrap user not found...")` if user is None
     - Returns `user.id`
     - Has a `# TODO: V1 single-user workaround — in multi-user future, _run_task_inference needs to know which user's credentials to use` comment
   - Add a `_build_calendar_provider(db: Session, user_id: int) -> GoogleCalendarProvider` helper that returns `GoogleCalendarProvider(user_id, db)` with structlog info event `calendar_provider_constructed`
   - Update `_build_resume_service` signature to accept `user_id: int` parameter; replace `_build_calendar_adapter()` call with `_build_calendar_provider(db=session, user_id=user_id)` where `session` is the `Session` argument already passed in
   - Update the `run()` function: inside the `with SessionLocal() as session:` block, call `user_id = _resolve_bootstrap_user_id(session)` and pass `user_id` to `_build_resume_service(session, handlers=configured_handlers, user_id=user_id)`

2. **Edit `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`**:
   - Add top-level imports: `from helm_providers import GoogleCalendarProvider`, `from helm_storage.repositories.users import get_user_by_telegram_id`
   - Add a module-level helper `_parse_telegram_user_id(submitted_by: str) -> int | None` that:
     - If `submitted_by` starts with `"telegram:"`, returns `int(submitted_by.split(":", 1)[1])`
     - Otherwise returns `None`
     - Handles `ValueError` gracefully (returns `None`)
   - Add a module-level helper `_resolve_user_id(submitted_by: str, db: Session) -> int` that:
     - Calls `_parse_telegram_user_id(submitted_by)` — if it returns a telegram ID, calls `get_user_by_telegram_id(telegram_id, db)` 
     - If user found, returns `user.id`
     - Falls back to: reads `TELEGRAM_ALLOWED_USER_ID` from env, looks up by that
     - If still no user found, raises `RuntimeError(f"No user found for submitted_by={submitted_by}")`
   - In `execute_task_run`:
     - Remove the lazy imports of `_build_calendar_adapter` and `_build_validator_registry` from `helm_worker.jobs.workflow_runs`
     - Keep the lazy import of `_build_validator_registry` (it's still needed and still comes from `workflow_runs`)
     - Inside the existing `with SessionLocal() as session:` block, call `user_id = _resolve_user_id(submitted_by_for_run, session)` where `submitted_by_for_run` is obtained from the run record. However, `execute_task_run` doesn't have `submitted_by` — it has `run_id`. Fetch the run: `from helm_storage.repositories import get_workflow_run` or query directly. **Actually**, looking at the code more carefully: `execute_task_run` creates the `CalendarAgentOutput` and `ScheduleBlock` *before* opening the session, then opens `SessionLocal()` to call `complete_current_step`. The provider is passed to `WorkflowOrchestrationService` inside the session block. The `submitted_by` is not available to `execute_task_run` directly — it only has `run_id`, `semantics`, and `request_text`. The simplest approach: add `submitted_by: str = ""` as an optional keyword parameter to `execute_task_run` and thread it from the caller in `task.py`. But `task.py` calls `svc.execute_task_run(run_id, semantics=semantics, request_text=request_text)` — and the caller (`_run_task_async`) has `update.effective_user.id` available. **Simpler approach**: don't parse `submitted_by` at all in `execute_task_run`. Instead, use the `TELEGRAM_ALLOWED_USER_ID` env var lookup as the V1 fallback (same as the worker path). This keeps the signature unchanged and avoids threading data through callers. Use `_resolve_user_id("", session)` which falls through to the env var lookup path.
     - Actually, even simpler: the run record has `submitted_by` stored. Fetch the run from the session to get `submitted_by`, then parse it. This is cleaner and doesn't require signature changes. Inside the `with SessionLocal() as session:` block: `run = session.get(WorkflowRunORM, run_id)` then `user_id = _resolve_user_id(run.submitted_by, session)`.
     - Replace `calendar_system_adapter=_build_calendar_adapter()` with `calendar_system_adapter=GoogleCalendarProvider(user_id, session)` (or use `_build_calendar_provider(session, user_id)` if the helper is importable)
   - In `execute_after_approval`:
     - Remove the lazy import of `_build_resume_service` from `workflow_runs`
     - Keep the lazy import of `_build_specialist_steps` from `workflow_runs` (still needed)
     - Import `_build_resume_service` at top level or keep lazy (the function now needs `user_id`)
     - Inside the `with SessionLocal() as session:` block, fetch the run to get `submitted_by`, resolve `user_id`, then call `_build_resume_service(session, handlers=handlers, user_id=user_id)`
   - Need to import `WorkflowRunORM` from `helm_storage.models` to fetch the run record

3. **Add import for `WorkflowRunORM`** in `workflow_status_service.py`:
   - `from helm_storage.models import WorkflowRunORM`

4. **Verify `_build_resume_service` callers**: The `run()` function in `workflow_runs.py` and `execute_after_approval` in `workflow_status_service.py` both call `_build_resume_service`. Both must now pass `user_id`.

5. **Clean up the return type annotation** on `_build_calendar_adapter` — since the function is deleted, the `GoogleCalendarAdapter | StubCalendarSystemAdapter` return type goes away.

6. **Run import smoke tests**:
   - `cd /Users/ankush/git/helm/.gsd/worktrees/M005 && uv run python -c "import helm_telegram_bot.services.workflow_status_service; print('ok')"`
   - `cd /Users/ankush/git/helm/.gsd/worktrees/M005 && uv run python -c "import helm_worker.jobs.workflow_runs; print('ok')"`

7. **Run ruff**:
   - `cd /Users/ankush/git/helm/.gsd/worktrees/M005 && uv run ruff check apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py apps/worker/src/helm_worker/jobs/workflow_runs.py`

## Must-Haves

- [ ] `_build_calendar_adapter()` function deleted from `workflow_runs.py`
- [ ] `GoogleCalendarAdapter` and `GoogleCalendarAuth` imports removed from `workflow_runs.py`
- [ ] `StubCalendarSystemAdapter` import removed from `workflow_runs.py` (keep `StubTaskSystemAdapter`)
- [ ] `GoogleCalendarProvider` constructed with `user_id` + `db` in `execute_task_run`, `execute_after_approval`, and `_build_resume_service`
- [ ] User lookup from `submitted_by` field (parse `"telegram:{id}"`) in telegram inline path
- [ ] Worker recovery path uses `TELEGRAM_ALLOWED_USER_ID` env var to find bootstrap user
- [ ] No references to `helm_connectors.google_calendar` in either file
- [ ] Both files pass `ruff check`
- [ ] Both files importable without errors

## Verification

- `uv run python -c "import helm_telegram_bot.services.workflow_status_service; print('ok')"` succeeds
- `uv run python -c "import helm_worker.jobs.workflow_runs; print('ok')"` succeeds
- `rg "_build_calendar_adapter" apps/ -t py` returns 0 results
- `rg "helm_connectors.google_calendar" apps/telegram-bot/src/ apps/worker/src/ -t py` returns 0 results
- `uv run ruff check apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py apps/worker/src/helm_worker/jobs/workflow_runs.py` passes

## Observability Impact

- Signals added: structlog `calendar_provider_constructed` (info, fields: user_id, source) in `_build_calendar_provider` helper
- Failure state exposed: `RuntimeError("No user found...")` and `RuntimeError("No Google credentials for user_id=...")` replace the silent stub fallback — these are hard errors now, not degraded modes
- How a future agent inspects this: grep for `calendar_provider_constructed` in worker/bot logs to confirm provider was built with a real user_id

## Inputs

- `packages/providers/src/helm_providers/google_calendar.py` — `GoogleCalendarProvider(user_id, db)` constructor from S02; satisfies `CalendarSystemAdapter` protocol
- `packages/storage/src/helm_storage/repositories/users.py` — `get_user_by_telegram_id(telegram_user_id, db)` from S01
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — current file with `_build_calendar_adapter()` to replace
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — current file with lazy imports of `_build_calendar_adapter`

## Expected Output

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `_build_calendar_adapter` deleted; `_resolve_bootstrap_user_id` and `_build_calendar_provider` added; `_build_resume_service` now accepts `user_id`; `run()` passes `user_id` from bootstrap lookup
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — top-level `GoogleCalendarProvider` import; `_parse_telegram_user_id` and `_resolve_user_id` helpers; `execute_task_run` and `execute_after_approval` fetch run record, resolve user, construct provider
