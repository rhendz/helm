---
estimated_steps: 7
estimated_files: 7
---

# T01: Migrate agenda.py + API workflow_status_service.py to GoogleCalendarProvider; delete google_calendar.py; rewrite test_agenda_command.py

**Slice:** S04 — Replace Calendar Connector in Worker + Bot
**Milestone:** M005

## Description

This task eliminates all `GoogleCalendarAdapter` and `GoogleCalendarAuth` usage from production source code and unit tests. Two call sites remain that use the bespoke connector: `agenda.py` (telegram bot) and `apps/api/services/workflow_status_service.py`. Both get rewritten to construct `GoogleCalendarProvider(user_id, db)` from `helm_providers`. After the source rewrites, `packages/connectors/google_calendar.py` is deleted and its exports are removed from `__init__.py`. The `test_agenda_command.py` unit tests are rewritten to mock the new provider instead of the old adapter. Two obsolete unit test files (`test_google_calendar_adapter.py`, `test_google_calendar_auth.py`) are deleted.

**Relevant installed skill:** None specifically required — this is a Python module rewrite task.

## Steps

1. **Rewrite `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py`**

   Replace the current imports and construction:
   ```python
   # REMOVE these:
   from helm_connectors.google_calendar import GoogleCalendarAdapter, GoogleCalendarAuth
   
   # ADD these:
   from helm_providers import GoogleCalendarProvider
   from helm_storage.db import SessionLocal
   from helm_storage.repositories.users import get_user_by_telegram_id
   ```

   In the `handle` function, replace `adapter = GoogleCalendarAdapter(GoogleCalendarAuth())` with:
   ```python
   telegram_user_id = update.effective_user.id
   with SessionLocal() as db:
       user = get_user_by_telegram_id(telegram_user_id, db)
       if user is None:
           await update.message.reply_text("No Helm user found for your Telegram account.")
           return
       provider = GoogleCalendarProvider(user.id, db)
       events = provider.list_today_events(
           calendar_id="primary",
           timezone=tz,
       )
   ```
   
   The rest of the handler (formatting events, reply) stays inside the `with SessionLocal() as db:` block — but only the provider call needs the session. The formatting + reply can be outside the `with` block since `events` is a plain list of dicts.

   Keep `reject_if_unauthorized` and `get_settings` unchanged. Ensure imports are isort-ordered (ruff I001).

2. **Rewrite `apps/api/src/helm_api/services/workflow_status_service.py` constructor**

   Current code (lines 7-11 imports, lines 63-73 constructor):
   ```python
   from helm_connectors import (
       GoogleCalendarAdapter,
       GoogleCalendarAuth,
       StubCalendarSystemAdapter,
       StubTaskSystemAdapter,
   )
   ```

   Replace with:
   ```python
   import os
   
   from helm_connectors import (
       StubCalendarSystemAdapter,
       StubTaskSystemAdapter,
   )
   from helm_providers import GoogleCalendarProvider
   from helm_storage.repositories.users import get_user_by_telegram_id
   ```

   In the `__init__` method, replace the try/except block (lines ~66-73):
   ```python
   # OLD:
   if calendar_system_adapter is None:
       try:
           auth = GoogleCalendarAuth()
           calendar_system_adapter = GoogleCalendarAdapter(auth)
       except ValueError:
           calendar_system_adapter = StubCalendarSystemAdapter()
   
   # NEW:
   if calendar_system_adapter is None:
       telegram_user_id_str = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
       if telegram_user_id_str:
           user = get_user_by_telegram_id(int(telegram_user_id_str), session)
           if user is not None:
               calendar_system_adapter = GoogleCalendarProvider(user.id, session)
       if calendar_system_adapter is None:
           calendar_system_adapter = StubCalendarSystemAdapter()
   ```
   
   **Critical constraint:** The `StubCalendarSystemAdapter()` fallback MUST be preserved. Many integration tests construct `WorkflowStatusService(session)` without seeding a user row or setting `TELEGRAM_ALLOWED_USER_ID`. Without the stub fallback, these tests break.

3. **Delete `packages/connectors/src/helm_connectors/google_calendar.py`**

   ```bash
   rm packages/connectors/src/helm_connectors/google_calendar.py
   ```

4. **Update `packages/connectors/src/helm_connectors/__init__.py`**

   Remove the `google_calendar` import line and the two exports:
   ```python
   # BEFORE:
   from helm_connectors.calendar_system import StubCalendarSystemAdapter
   from helm_connectors.google_calendar import GoogleCalendarAdapter, GoogleCalendarAuth
   from helm_connectors.task_system import StubTaskSystemAdapter
   
   __all__ = [
       "GoogleCalendarAdapter",
       "GoogleCalendarAuth",
       "StubCalendarSystemAdapter",
       "StubTaskSystemAdapter",
   ]
   
   # AFTER:
   from helm_connectors.calendar_system import StubCalendarSystemAdapter
   from helm_connectors.task_system import StubTaskSystemAdapter
   
   __all__ = [
       "StubCalendarSystemAdapter",
       "StubTaskSystemAdapter",
   ]
   ```

5. **Rewrite `tests/unit/test_agenda_command.py`**

   The tests currently monkeypatch `agenda.GoogleCalendarAdapter` and `agenda.GoogleCalendarAuth`. After the rewrite, these names don't exist on the module. Replace with patches targeting the new names:
   
   - Patch `agenda.get_user_by_telegram_id` → return a mock user object with `.id = 1`
   - Patch `agenda.SessionLocal` → return a mock context manager (so no real DB session is opened)
   - Patch `agenda.GoogleCalendarProvider` → a class whose `list_today_events` returns the test data
   
   The cleanest approach: create a simple mock provider class or use `MagicMock`. For each test:
   ```python
   # Replace these two patches:
   monkeypatch.setattr(agenda.GoogleCalendarAdapter, "list_today_events", lambda self, calendar_id, timezone: sample_events)
   monkeypatch.setattr(agenda.GoogleCalendarAuth, "__init__", lambda self: None)
   
   # With these:
   mock_user = type("User", (), {"id": 1})()
   monkeypatch.setattr(agenda, "get_user_by_telegram_id", lambda tid, db: mock_user)
   monkeypatch.setattr(agenda, "SessionLocal", _mock_session_local)
   monkeypatch.setattr(agenda, "GoogleCalendarProvider", lambda user_id, db: _FakeProvider(sample_events))
   ```
   
   Where `_mock_session_local` is a context manager that yields a MagicMock and `_FakeProvider` is a simple class with `list_today_events(calendar_id, timezone)` returning the given events.

   All 4 test cases must survive:
   - `test_agenda_formats_events_correctly` — events with dateTime, check time formatting
   - `test_agenda_empty_day_shows_no_events_message` — empty list → "No events today"
   - `test_agenda_unauthorized_user_gets_rejected` — auth guard blocks, adapter not called
   - `test_agenda_all_day_event_shows_all_day_label` — events with date (not dateTime) → "All day"

6. **Delete obsolete unit test files**

   ```bash
   rm tests/unit/test_google_calendar_adapter.py
   rm tests/unit/test_google_calendar_auth.py
   ```

7. **Run ruff and fix any lint issues**

   ```bash
   uv run ruff check apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py \
     apps/api/src/helm_api/services/workflow_status_service.py \
     packages/connectors/src/helm_connectors/__init__.py \
     tests/unit/test_agenda_command.py --fix
   ```
   
   The existing `agenda.py` already has an I001 (unsorted imports) — the rewrite should fix this.

## Must-Haves

- [ ] `agenda.py` uses `GoogleCalendarProvider(user_id, db)` — no `GoogleCalendarAdapter` or `GoogleCalendarAuth`
- [ ] `api/services/workflow_status_service.py` uses `GoogleCalendarProvider(user_id, session)` with `StubCalendarSystemAdapter` fallback preserved
- [ ] `packages/connectors/google_calendar.py` deleted
- [ ] `packages/connectors/__init__.py` exports only `StubCalendarSystemAdapter` and `StubTaskSystemAdapter`
- [ ] `test_agenda_command.py` patches new names; all 4 tests pass
- [ ] `test_google_calendar_adapter.py` and `test_google_calendar_auth.py` deleted
- [ ] `ruff check` clean on all modified files

## Verification

- `uv run pytest tests/unit/test_agenda_command.py -v` → 4 passed
- `rg "GoogleCalendarAdapter\|GoogleCalendarAuth" apps/ tests/unit/ -t py` → 0 results (exit code 1)
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c "import helm_telegram_bot.commands.agenda; print('ok')"` → ok
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c "import helm_api.services.workflow_status_service; print('ok')"` → ok
- `ls packages/connectors/src/helm_connectors/google_calendar.py 2>&1` → "No such file"
- `uv run python -c "from helm_connectors import StubCalendarSystemAdapter, StubTaskSystemAdapter; print('ok')"` → ok (stubs still importable)
- `uv run ruff check apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py apps/api/src/helm_api/services/workflow_status_service.py packages/connectors/src/helm_connectors/__init__.py tests/unit/test_agenda_command.py` → 0 errors

## Inputs

- `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py` — current file using `GoogleCalendarAdapter(GoogleCalendarAuth())`; 46 lines
- `apps/api/src/helm_api/services/workflow_status_service.py` — current file importing `GoogleCalendarAdapter`/`GoogleCalendarAuth` from `helm_connectors`; 1168 lines; only the import block (lines 7-11) and constructor (lines ~55-78) need changes
- `tests/unit/test_agenda_command.py` — 162 lines; 4 async tests that monkeypatch `agenda.GoogleCalendarAdapter` and `agenda.GoogleCalendarAuth`
- `packages/connectors/src/helm_connectors/__init__.py` — exports to trim
- `packages/connectors/src/helm_connectors/google_calendar.py` — file to delete
- S02 established `GoogleCalendarProvider(user_id, db)` in `packages/providers/src/helm_providers/google_calendar.py` with identical `list_today_events(calendar_id, timezone)` signature
- S01 established `get_user_by_telegram_id(telegram_user_id, db) → UserORM | None` in `packages/storage/src/helm_storage/repositories/users.py`
- S01 established `SessionLocal` in `packages/storage/src/helm_storage/db.py`
- The `task.py` handler (already migrated) is the canonical pattern for telegram bot → DB session → user lookup → provider construction

## Expected Output

- `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py` — rewritten to use `GoogleCalendarProvider`
- `apps/api/src/helm_api/services/workflow_status_service.py` — constructor updated to use `GoogleCalendarProvider` with stub fallback
- `packages/connectors/src/helm_connectors/__init__.py` — `GoogleCalendarAdapter`/`GoogleCalendarAuth` removed
- `packages/connectors/src/helm_connectors/google_calendar.py` — deleted
- `tests/unit/test_agenda_command.py` — rewritten to mock new provider names; 4 tests pass
- `tests/unit/test_google_calendar_adapter.py` — deleted
- `tests/unit/test_google_calendar_auth.py` — deleted

## Observability Impact

**Signals that change after this task:**
- The `/agenda` bot handler now emits `GoogleCalendarProvider` structlog events (`list_today_events`, `list_today_events_complete`) instead of the old connector's events. These fire whenever a user runs `/agenda` successfully.
- If no Helm user row exists for the Telegram account, the handler logs nothing from the provider (exits early with a reply message). This is the observable failure path.
- `WorkflowStatusService` no longer emits `GoogleCalendarAdapter` construction errors in logs. When `TELEGRAM_ALLOWED_USER_ID` is set and a user row exists, `GoogleCalendarProvider` events appear; otherwise the service silently falls back to `StubCalendarSystemAdapter`.

**How to inspect this task at runtime:**
- Check structlog output for `list_today_events` / `list_today_events_complete` events bound with `user_id` to confirm the provider was constructed from a real DB user row.
- Absence of these events during `/agenda` means either the user row is missing (handler exits with "No Helm user found") or the DB session failed.
- `OPERATOR_TIMEZONE` value appears in the `/agenda` reply header confirming settings are loaded.

**Failure visibility:**
- `"No Helm user found for your Telegram account."` reply → user row not seeded, `get_user_by_telegram_id` returned `None`.
- Import error on `helm_providers` at bot startup → package not installed or `GoogleCalendarProvider` not exported.
- `StubCalendarSystemAdapter` used silently in API → `TELEGRAM_ALLOWED_USER_ID` unset or user row missing (expected in integration tests).
