---
estimated_steps: 7
estimated_files: 7
---

# T03: Remove legacy stubs and implement /agenda command

**Slice:** S06 — Dev experience, observability, and cleanup
**Milestone:** M004

## Description

Two cleanup/gap-fill tasks combined because the cleanup is a small verification + edit, and `/agenda` is a focused net-new feature.

**Legacy cleanup (R118):** After the T01 merge, `workflow_runs.py` should already use `compute_reference_week` instead of hardcoded dates, and `parse_local_slot` instead of `_parse_slot_from_title`. Verify and remove any residual stubs. Also remove the "S01 stub" comment from `scheduling.py`.

**`/agenda` gap fill:** The S04/T02 commit (`e86f7e3`) claimed to add `list_today_events()` and `agenda.py` but the actual diff only changed `.gitignore` and the roadmap. Neither file exists on any branch. This task creates them fresh.

## Steps

1. **Verify and clean legacy stubs from `workflow_runs.py`.** Run:
   ```bash
   grep -n "2026, 3, 16\|_parse_slot_from_title\|_DAY_OFFSETS\|_TIME_PATTERN" apps/worker/src/helm_worker/jobs/workflow_runs.py
   ```
   If any matches remain (the merge in T01 should have brought in milestone/M004's refactored version which removed them), delete the offending lines/functions. Specifically:
   - `_DAY_OFFSETS` dict (maps day names to offsets)
   - `_TIME_PATTERN` regex (matches time patterns like "10am")
   - `_parse_slot_from_title()` function (replaced by `parse_local_slot` from shared primitives)
   - `base = datetime(2026, 3, 16, 9, tzinfo=UTC)` (replaced by `compute_reference_week`)
   - **KEEP `_RANGE_PATTERN`** — it's used by `_parse_duration_from_title` which is still needed.
   
   Also verify that `_candidate_slots` function now calls `compute_reference_week` instead of using the hardcoded date.

2. **Remove "S01 stub" comment from `scheduling.py`.** In `packages/orchestration/src/helm_orchestration/scheduling.py`, find any comment containing "S01 stub" (near `ConditionalApprovalPolicy`) and remove it. The class is fully implemented now.

3. **Add `list_today_events` to `GoogleCalendarAdapter`.** In `packages/connectors/src/helm_connectors/google_calendar.py`, add a new method:
   ```python
   def list_today_events(self, calendar_id: str, timezone: ZoneInfo) -> list[dict]:
       """Return today's events from the calendar in operator local time."""
       service = self._build_service()
       now_local = datetime.now(timezone)
       start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
       end_of_day = start_of_day + timedelta(days=1)
       
       time_min = start_of_day.isoformat()
       time_max = end_of_day.isoformat()
       
       result = service.events().list(
           calendarId=calendar_id,
           timeMin=time_min,
           timeMax=time_max,
           singleEvents=True,
           orderBy="startTime",
       ).execute()
       
       return result.get("items", [])
   ```
   Add `from datetime import datetime, timedelta` and `from zoneinfo import ZoneInfo` imports at the top if not already present. Add a structlog event for the call.

4. **Create `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py`.** New file with this structure:
   ```python
   """Handler for /agenda command — shows today's calendar events."""
   from datetime import datetime
   from zoneinfo import ZoneInfo
   
   from telegram import Update
   from telegram.ext import ContextTypes
   
   from helm_telegram_bot.commands.common import reject_if_unauthorized
   from helm_telegram_bot.config import get_settings
   from helm_connectors.google_calendar import GoogleCalendarAdapter
   from helm_observability.logging import get_logger
   
   logger = get_logger("helm_telegram_bot.commands.agenda")
   
   
   async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
       if await reject_if_unauthorized(update, context):
           return
       
       settings = get_settings()
       tz = ZoneInfo(settings.operator_timezone)
       
       adapter = GoogleCalendarAdapter()
       events = adapter.list_today_events(
           calendar_id="primary",
           timezone=tz,
       )
       
       if not events:
           await update.message.reply_text("📅 No events today.")
           return
       
       lines = [f"📅 Today's agenda ({tz}):"]
       for event in events:
           summary = event.get("summary", "(no title)")
           start_raw = event.get("start", {}).get("dateTime")
           if start_raw:
               start_dt = datetime.fromisoformat(start_raw).astimezone(tz)
               time_str = start_dt.strftime("%-I:%M %p")
           else:
               time_str = "All day"
           lines.append(f"• {time_str} — {summary}")
       
       await update.message.reply_text("\n".join(lines))
   ```
   
   **Important:** Use the same auth guard pattern as other commands (`reject_if_unauthorized`). Use `get_settings()` to get `operator_timezone` (same pattern as `status.py`).

5. **Register `/agenda` handler in `main.py`.** In `apps/telegram-bot/src/helm_telegram_bot/main.py`:
   - Add `agenda` to the imports from `helm_telegram_bot.commands`
   - Add `application.add_handler(CommandHandler("agenda", agenda.handle))` in the handler registration section (alphabetical order — should go near the top of the handler list, after `approve`)

6. **Write `tests/unit/test_agenda_command.py`.** Create a unit test file following the same pattern as `test_task_command.py` and `test_status_command.py`:
   - Test: events are formatted correctly (mock `GoogleCalendarAdapter.list_today_events` to return 2 sample events with `start.dateTime` in ISO format; verify reply contains event summaries and formatted times)
   - Test: empty day shows "No events today" message
   - Test: unauthorized user gets rejected (mock `reject_if_unauthorized` to return True; verify no reply sent)
   
   Use `monkeypatch` to mock the adapter and settings. Set `OPERATOR_TIMEZONE=America/Los_Angeles` in test env if needed (should be set by root `tests/conftest.py`).

7. **Run verification.** Execute:
   ```bash
   # Legacy cleanup check
   grep -n "2026, 3, 16\|_parse_slot_from_title\|_DAY_OFFSETS\|_TIME_PATTERN" apps/worker/src/helm_worker/jobs/workflow_runs.py
   # Should return nothing
   
   # Agenda test
   uv run --frozen pytest tests/unit/test_agenda_command.py -v
   
   # Full suite regression check
   uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py -q
   ```

8. **Commit.** `git add -A && git commit -m "feat(S06/T03): Remove legacy scheduling stubs and add /agenda command"`

## Must-Haves

- [ ] No `_DAY_OFFSETS`, `_TIME_PATTERN`, `_parse_slot_from_title`, or hardcoded `datetime(2026, 3, 16, ...)` in `workflow_runs.py`
- [ ] `_RANGE_PATTERN` is still present in `workflow_runs.py` (used by `_parse_duration_from_title`)
- [ ] No "S01 stub" comment in `scheduling.py`
- [ ] `GoogleCalendarAdapter.list_today_events()` method exists and works
- [ ] `agenda.py` command handler exists with auth guard
- [ ] `/agenda` handler registered in `main.py`
- [ ] `test_agenda_command.py` has tests for events format, empty day, and auth rejection
- [ ] Full test suite still passes (440+ tests, 0 failures)

## Verification

- `grep -n "2026, 3, 16\|_parse_slot_from_title\|_DAY_OFFSETS\|_TIME_PATTERN" apps/worker/src/helm_worker/jobs/workflow_runs.py` → no output
- `grep -n "S01 stub" packages/orchestration/src/helm_orchestration/scheduling.py` → no output
- `grep "list_today_events" packages/connectors/src/helm_connectors/google_calendar.py` → shows the method
- `grep "agenda" apps/telegram-bot/src/helm_telegram_bot/main.py` → shows import and handler registration
- `uv run --frozen pytest tests/unit/test_agenda_command.py -v` → all tests pass
- `uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py -q` → 443+ passed, 0 failures

## Inputs

- T01 completed: `milestone/M004` merged, all S01–S04 code on `main`
- T02 completed: devex deps added (no direct dependency, but pyproject.toml was modified)
- `packages/connectors/src/helm_connectors/google_calendar.py` — existing adapter with `upsert_calendar_block` and `reconcile_calendar_block` methods (pattern to follow)
- `apps/telegram-bot/src/helm_telegram_bot/commands/status.py` — `/status` handler (pattern to follow for `/agenda`)
- `tests/unit/test_status_command.py` — test pattern to follow for `test_agenda_command.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/common.py` — `reject_if_unauthorized` auth guard

## Expected Output

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — legacy stubs removed
- `packages/orchestration/src/helm_orchestration/scheduling.py` — "S01 stub" comment removed
- `packages/connectors/src/helm_connectors/google_calendar.py` — `list_today_events()` method added
- `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py` — new file with `/agenda` handler
- `apps/telegram-bot/src/helm_telegram_bot/main.py` — `/agenda` handler registered
- `tests/unit/test_agenda_command.py` — new file with 3+ unit tests
