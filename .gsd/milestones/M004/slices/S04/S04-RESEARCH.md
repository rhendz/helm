# S04: Telegram UX Overhaul and Proactive Notifications — Research

**Date:** 2026-03-17

## Summary

S04 is well-understood, additive work. All the machinery it needs already exists: DB queries for pending approvals and recent runs, `settings.operator_timezone` available through `BotSettings`, `TelegramDigestDeliveryService.deliver()` for proactive push, and `GoogleCalendarAdapter._get_service()` for live API calls. The slice has four distinct deliverables: (1) `/status` command, (2) `/agenda` command, (3) proactive approval notification for the weekly workflow path, and (4) clean default output enforcement. None of these require new infrastructure; they wire and format existing data.

The two meaningful design questions are: where proactive notifications get triggered for the weekly workflow (currently there is no notification at all when the polling worker advances a weekly run to `awaiting_approval`), and how `/agenda` reads from Google Calendar (the existing `GoogleCalendarAdapter` has no `list_events` method — a small addition needed). Everything else is formatting and plumbing.

The `/task` fast path already pushes a proactive notification inline in `_run_task_async` when `needs_action=True`. The gap is the weekly workflow path, where the worker job runs `resume_runnable_runs()` synchronously and advances a run to `awaiting_approval` with no side-effect notification. The fix is to add a notification call after the worker advances a run to that state. Since the worker has no running event loop, `TelegramDigestDeliveryService.deliver()` with its `asyncio.run()` call works correctly there.

## Recommendation

Build in four tasks:
1. **`/status` command** — new `commands/status.py`. Queries `list_runs_needing_action()` and `list_recent_runs()`, formats operator-facing output including OPERATOR_TIMEZONE. Register in `main.py`.
2. **`/agenda` command** — new `commands/agenda.py`. Adds `list_today_events(calendar_id)` to `GoogleCalendarAdapter` (calls `events().list()` with day-range `timeMin`/`timeMax`). Displays events in local time using `settings.operator_timezone`. Register in `main.py`.
3. **Proactive notification for weekly workflow** — add `notify_approval_needed(run_id, proposal_summary)` to `TelegramDigestDeliveryService` (or a new `NotificationService`). Call it from `workflow_runs.run()` after `resume_runnable_runs()` returns runs that reached `needs_action=True`.
4. **Unit tests** — cover all three commands and the notification path.

## Implementation Landscape

### Key Files

- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` — `_format_run()` is the existing verbose formatter (lines 33–150). It shows `run_id`, `step=`, `paused=`, sync timeline by default. This is the "debug output" D008 explicitly targets. Do not change this file for default output — it's preserved for power users. `/status` is a separate command with its own clean formatter.
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — `list_runs_needing_action()` and `list_recent_runs()` already exist (lines 129, 133). Both return dicts with `id`, `status`, `needs_action`, `approval_checkpoint`, `workflow_type`, `completion_summary`. These are the data sources for `/status`.
- `apps/telegram-bot/src/helm_telegram_bot/config.py` — `BotSettings` extends `RuntimeAppSettings`. `get_settings().operator_timezone` is already a validated IANA string. No changes needed to config.
- `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` — `TelegramDigestDeliveryService.deliver(text)` sends a message via `asyncio.run()`. Works from worker context (no running loop). For a proactive approval notification, add `notify_approval_needed(run_id, proposal_summary)` method here — or inline it as a second method that formats the message and calls `deliver()`.
- `apps/telegram-bot/src/helm_telegram_bot/main.py` — registration site for new `/status` and `/agenda` command handlers. Two `application.add_handler(CommandHandler(...))` calls needed.
- `packages/connectors/src/helm_connectors/google_calendar.py` — `GoogleCalendarAdapter` class (line 139). Has `_get_service()` returning a `googleapiclient` resource. Has `upsert_calendar_block()` and `reconcile_calendar_block()` but **no `list_events` method**. Need to add `list_today_events(calendar_id: str) -> list[dict]` that calls `service.events().list(calendarId=calendar_id, timeMin=..., timeMax=..., singleEvents=True, orderBy="startTime").execute()`.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `run()` function (line 53) calls `resume_service.resume_runnable_runs()` and returns run IDs. No notification side effects. This is where proactive push for weekly workflow needs to be wired: after `resumed = resume_service.resume_runnable_runs()`, query DB to find any run in `resumed` that now has `needs_action=True` and push a notification for each.
- `tests/unit/test_workflow_telegram_commands.py` — existing pattern file for Telegram command unit tests. New tests follow the same `_Service`/`_Update`/`_Context` pattern.

### Data Available for `/status`

From `list_runs_needing_action()` and `list_recent_runs()`, the run dict contains:
- `id` (int)
- `status` (str: "active", "completed", "failed")
- `needs_action` (bool)
- `workflow_type` (str: "task_quick_add" or "weekly_scheduling")
- `approval_checkpoint` (dict | None) — has `target_artifact_id`, `proposal_summary`
- `completion_summary` (dict | None) — has `headline`
- `current_step` (str | None) — do NOT expose in default output (D008)

Clean `/status` format:
```
📋 Helm Status
Timezone: America/Los_Angeles

⏳ Pending Approvals (1):
• Run 7 — Schedule: book dentist tomorrow at 2pm
  Type /approve 7 <artifact_id> to confirm

✅ Recent Completions (2):
• Run 5 — Scheduled 3 blocks for the week
• Run 6 — Task scheduled: buy groceries

No active workflows.
```

### Data Available for `/agenda`

Google Calendar `events().list()` returns event objects with:
- `summary` (title)
- `start.dateTime` or `start.date` (ISO datetime or date string)
- `end.dateTime` or `end.dateTime`
- `status` ("confirmed", "cancelled")

The `list_today_events` method needs to compute:
- `timeMin`: today at 00:00:00 in OPERATOR_TIMEZONE, converted to RFC3339
- `timeMax`: today at 23:59:59 in OPERATOR_TIMEZONE, converted to RFC3339

`to_utc()` from `helm_orchestration` handles timezone conversion. Display times must be formatted back to local time using `ZoneInfo(settings.operator_timezone)`.

### Proactive Notification for Weekly Workflow

The gap: `workflow_runs.run()` calls `resume_runnable_runs()` which can advance a weekly run to `awaiting_approval` / `needs_action=True`. Nothing currently notifies the operator.

Pattern from the `/task` path (inline in `_run_task_async`):
```python
if needs_action and approval_checkpoint:
    artifact_id = approval_checkpoint.get("target_artifact_id")
    proposal_summary = approval_checkpoint.get("proposal_summary", "")
    await update.message.reply_text(f"⏳ Schedule proposal ready...")
```

For the worker path, the notification needs to happen outside the PTB async context. The correct approach:
1. After `resumed = resume_service.resume_runnable_runs()`, query `WorkflowStatusService.get_run_detail(run_id)` for each resumed run.
2. For any run where `result["needs_action"] is True`, call `TelegramDigestDeliveryService().deliver(message)`.
3. `asyncio.run()` inside `deliver()` is safe here because the worker has no running event loop.

**Important:** `TelegramDigestDeliveryService` uses `get_settings()` from `helm_telegram_bot.config` which imports `BotSettings`. `BotSettings` extends `RuntimeAppSettings` which requires `OPERATOR_TIMEZONE`. This import is safe in the worker since the worker already requires `OPERATOR_TIMEZONE` via its own `settings`.

### Build Order

1. **`/status` command** first (no external deps beyond existing service methods). Fastest value.
2. **`list_today_events` in GoogleCalendarAdapter** + **`/agenda` command** second. The calendar adapter method is the only new non-trivial code.
3. **Proactive notification** third. Requires modifying `workflow_runs.run()` — must not regress existing worker tests.
4. **Tests** woven in with each task.

### Verification Approach

```bash
# 1. Import check for new commands
OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c \
  "from helm_telegram_bot.commands import status, agenda; print('imports ok')"

# 2. Handler registration
grep -n "status.handle\|agenda.handle" apps/telegram-bot/src/helm_telegram_bot/main.py

# 3. Unit tests
OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_status_command.py -v
OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_agenda_command.py -v

# 4. No regressions
OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py
```

For manual verification: `/status` should show pending approvals with `/approve` hint and the OPERATOR_TIMEZONE. `/agenda` should show today's calendar events in local time. Worker job should push a Telegram message when a weekly workflow reaches `awaiting_approval`.

## Constraints

- `TelegramDigestDeliveryService.deliver()` uses `asyncio.run()` — call it only from non-async context (worker). If ever called from PTB handler async context, use `loop.run_in_executor` instead. For S04, proactive push is wired in the worker's synchronous `workflow_runs.run()` — safe.
- `BotSettings.operator_timezone` is available in all telegram-bot handlers via `get_settings()`. For `/status` timezone display, read it from `get_settings()` directly — no import from `helm_worker.config`.
- `GoogleCalendarAdapter` is only instantiated if `GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN` are set (falls back to stub otherwise). `/agenda` should handle the stub case gracefully — either skip real Calendar fetch or surface "Calendar not configured."
- The `list_today_events` method should be added to `GoogleCalendarAdapter` only (not to the `CalendarSystemAdapter` protocol), since agenda is a read operation not part of the sync contract.
- Do not expose `current_step`, `paused_state`, run IDs in plain `/status` output (D008). These remain available via `/workflows` (power user command).

## Common Pitfalls

- **`asyncio.run()` in deliver()** — works from worker (synchronous), crashes if called from async PTB handler. Don't wire the proactive notification into any async PTB handler.
- **`get_settings()` is cached via `@lru_cache`** — safe to call from `/status` and `/agenda` handlers; returns same instance. Don't bypass cache.
- **`list_today_events` edge case: `start.date` vs `start.dateTime`** — all-day events use `start.date` (a date string without time), timed events use `start.dateTime`. The formatter must handle both.
- **`_build_calendar_adapter()` in workflow_runs.py returns a stub if credentials are missing** — `list_today_events` is on the real `GoogleCalendarAdapter` only; the stub won't have this method. The `/agenda` command must instantiate `GoogleCalendarAdapter` directly (mirroring `_build_calendar_adapter` logic) and handle the no-credentials case.
- **Proactive notification deduplication** — `resume_runnable_runs()` processes multiple runs per invocation. If two runs advance to `needs_action=True` in one poll cycle, both should generate notifications. No dedup needed for V1; just iterate over resumed runs.
