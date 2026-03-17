---
estimated_steps: 7
estimated_files: 3
---

# T02: Add `list_today_events` to GoogleCalendarAdapter and build `/agenda` command

**Slice:** S04 — Telegram UX Overhaul and Proactive Notifications
**Milestone:** M004

## Description

Add `list_today_events(calendar_id: str) -> list[dict]` to `GoogleCalendarAdapter` in `packages/connectors`. This method calls `service.events().list(...)` with `timeMin`/`timeMax` bounds computed from today's date in OPERATOR_TIMEZONE, returning raw event dicts with title, start time, and end time.

Then build `/agenda` command in a new `commands/agenda.py`. It instantiates `GoogleCalendarAdapter` directly (checking for credentials env vars), calls `list_today_events("primary")`, and formats the results as a concise list of events in operator local time. If credentials are missing, it returns "Calendar not configured." rather than crashing.

The new command is **not** registered in `main.py` in this task — T03 handles all registration.

**Key constraints:**
- `list_today_events` is added to `GoogleCalendarAdapter` only — NOT to the `CalendarSystemAdapter` protocol or the stub. It's a read-only agenda feature, not part of the sync contract.
- The formatter must handle both timed events (`start.dateTime` — ISO string with offset) and all-day events (`start.date` — a plain date string like `"2026-03-17"`).
- `/agenda` must import `GoogleCalendarAdapter` directly and guard on credential availability (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` env vars). Do not instantiate it via `_build_calendar_adapter()` from the worker (that requires worker config import).
- OPERATOR_TIMEZONE is read from `get_settings().operator_timezone` (BotSettings).

## Steps

1. **Add `list_today_events` to `GoogleCalendarAdapter`**
   - File: `packages/connectors/src/helm_connectors/google_calendar.py`
   - After the existing `reconcile_calendar_block` method, add:
     ```python
     def list_today_events(self, calendar_id: str) -> list[dict]:
         """Return today's events from the given calendar in chronological order.
         
         Each returned dict has keys: summary, start_dt (datetime or date string), end_dt, is_all_day.
         start_dt is a datetime object for timed events, a plain date string for all-day events.
         """
     ```
   - Use `os.environ["OPERATOR_TIMEZONE"]` (or import from `helm_runtime` if a cleaner path is available) to compute bounds; alternatively accept a `tz: ZoneInfo` parameter — but keep it simple: pass `ZoneInfo(os.environ["OPERATOR_TIMEZONE"])` from the method body
   - Compute `timeMin` = today at 00:00:00 in that timezone, converted to RFC3339 with offset
   - Compute `timeMax` = today at 23:59:59 in that timezone, converted to RFC3339 with offset
   - Call `service.events().list(calendarId=calendar_id, timeMin=..., timeMax=..., singleEvents=True, orderBy="startTime").execute()`
   - For each event in `result.get("items", [])`:
     - Skip if `event.get("status") == "cancelled"`
     - Parse `start.dateTime` as a timed event or `start.date` as an all-day event
     - Return a list of dicts: `{"summary": str, "start_dt": datetime | str, "end_dt": datetime | str, "is_all_day": bool}`
   - For timed events: parse `start.dateTime` (ISO string) to a timezone-aware datetime using `datetime.fromisoformat()`
   - For all-day events: return `start.date` as a plain string (no time component to display)
   - Use `_get_service()` to get the service object

2. **Create `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py`**
   - Auth guard: `reject_if_unauthorized(update, context)`
   - Credentials check: if any of `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` are absent from `os.environ`, reply with `"Calendar not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN to enable /agenda."` and return
   - Instantiate `GoogleCalendarAdapter(GoogleCalendarAuth())` inside the handler (do not cache at module level — credentials may not be set at import time)
   - Call `adapter.list_today_events("primary")`
   - Read timezone: `tz = ZoneInfo(get_settings().operator_timezone)`
   - Format response:
     - Header: `📅 Today's Agenda ({date_str} · {tz_name})\n`
     - For each timed event: `• {HH:MM}–{HH:MM} {title}` (times displayed in OPERATOR_TIMEZONE)
     - For each all-day event: `• All day — {title}`
     - If no events: `No events today.`
   - Timed events: convert `start_dt` to local time via `.astimezone(tz)` and format as `"%H:%M"`
   - Wrap in `try/except Exception` — if calendar API fails, reply with "Could not fetch calendar: {e}"
   - Imports: `from helm_connectors.google_calendar import GoogleCalendarAdapter, GoogleCalendarAuth`

3. **Create `tests/unit/test_agenda_command.py`**
   - Use `_Message` / `_Update` / `_Context` pattern (same as T01)
   - Patch `agenda.GoogleCalendarAdapter` with a fake class whose `list_today_events` returns controlled data
   - Patch `agenda.get_settings()` to return stub with `operator_timezone = "America/Los_Angeles"`
   - Patch `os.environ` or `agenda.os.environ` to control credential availability
   - Test 1: `test_agenda_no_credentials` — missing `GOOGLE_CLIENT_ID` env var → reply contains "Calendar not configured"
   - Test 2: `test_agenda_timed_events` — list_today_events returns one timed event with `is_all_day=False`, `start_dt=datetime(2026,3,17,10,0,tzinfo=ZoneInfo("America/Los_Angeles"))`, `summary="Dentist"` → reply contains "10:00" and "Dentist"
   - Test 3: `test_agenda_all_day_event` — list_today_events returns one all-day event with `is_all_day=True`, `start_dt="2026-03-17"`, `summary="Birthday"` → reply contains "All day" and "Birthday"
   - Test 4: `test_agenda_empty_calendar` — list_today_events returns `[]` → reply contains "No events today"
   - Test 5: `test_agenda_api_error` — list_today_events raises `Exception("API error")` → reply contains "Could not fetch calendar"
   - Test 6: `test_agenda_shows_timezone_in_header` — reply contains "America/Los_Angeles" or the display timezone name

## Must-Haves

- [ ] `GoogleCalendarAdapter.list_today_events(calendar_id)` exists, calls `events().list()`, handles `start.dateTime` (timed) and `start.date` (all-day) event shapes, skips cancelled events
- [ ] `/agenda` handler checks for credential env vars before instantiating adapter; returns "Calendar not configured" gracefully
- [ ] `/agenda` output shows events in OPERATOR_TIMEZONE with HH:MM format for timed events; "All day" prefix for all-day events
- [ ] `/agenda` wraps calendar API call in try/except with user-facing error message
- [ ] 6 unit tests in `test_agenda_command.py`, all passing
- [ ] `list_today_events` is NOT added to `CalendarSystemAdapter` protocol or any stub class

## Verification

```bash
OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c \
  "from helm_telegram_bot.commands import agenda; print('import ok')"
# → import ok

OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c \
  "from helm_connectors.google_calendar import GoogleCalendarAdapter; \
   import inspect; assert 'list_today_events' in dir(GoogleCalendarAdapter); print('method ok')"

# Confirm not added to protocol
OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c \
  "from helm_connectors import StubCalendarSystemAdapter; \
   assert not hasattr(StubCalendarSystemAdapter, 'list_today_events'); print('stub clean')"

OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_agenda_command.py -v
# → 6 passed
```

## Observability Impact

- Failure state exposed: if Calendar API raises (auth error, quota, network), the `try/except Exception` in the handler catches it and replies with the error message to the operator — no silent failures

## Inputs

- `packages/connectors/src/helm_connectors/google_calendar.py` — read the existing `GoogleCalendarAdapter` class (especially `_get_service()` on line ~150 and `upsert_calendar_block` for the `service.events()` usage pattern). The `_get_service()` method returns a `googleapiclient` resource. `list_today_events` uses `service.events().list(...).execute()`.
- S04-RESEARCH.md constraint: `list_today_events` on `GoogleCalendarAdapter` only — not on `CalendarSystemAdapter` protocol. `/agenda` instantiates `GoogleCalendarAdapter` directly, not via `_build_calendar_adapter()` (worker dependency).
- S04-RESEARCH.md pitfall: all-day events use `start.date` (date string), timed events use `start.dateTime` (ISO datetime string). Both must be handled.
- `apps/telegram-bot/src/helm_telegram_bot/commands/common.py` — `reject_if_unauthorized` auth guard pattern.

## Expected Output

- `packages/connectors/src/helm_connectors/google_calendar.py` — `list_today_events(calendar_id)` method added to `GoogleCalendarAdapter`
- `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py` — new file with async `handle(update, context)`, credential check, event formatting, error handling
- `tests/unit/test_agenda_command.py` — new file with 6 passing unit tests
