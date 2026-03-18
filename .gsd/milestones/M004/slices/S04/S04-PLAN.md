# S04: Telegram UX Overhaul and Proactive Notifications

**Goal:** `/status` shows pending approvals, recent actions, and active OPERATOR_TIMEZONE; `/agenda` shows today's Calendar events in local time; the weekly workflow pushes a proactive Telegram notification when it reaches `awaiting_approval`; one `/task` auto-places (high confidence, low disruption) and one triggers an approval request (ambiguous/disruptive); default output is concise and operator-facing.
**Demo:** Running `/status` returns operator-facing output listing pending approvals with `/approve` hints and the configured timezone. Running `/agenda` returns today's calendar events formatted in local time. Triggering a weekly workflow that reaches `awaiting_approval` fires a proactive Telegram push without polling.

## Must-Haves

- `/status` command registered and returning concise operator-facing output: pending approvals (with `/approve N M` hint), recent completions (last 5), and `OPERATOR_TIMEZONE` — no `current_step`, `paused_state`, or sync metadata by default (D008)
- `/agenda` command registered and returning today's Google Calendar events in operator local time, handling the no-credentials stub case gracefully
- `notify_approval_needed(run_id, proposal_summary)` method on `TelegramDigestDeliveryService` — callable from synchronous worker context via `asyncio.run()`
- Worker `workflow_runs.run()` calls `notify_approval_needed` for each run that advances to `needs_action=True` in a poll cycle
- `list_today_events(calendar_id)` added to `GoogleCalendarAdapter` (not to the stub or `CalendarSystemAdapter` protocol)
- All new commands produce concise operator-facing output by default — internal IDs, step names, artifact IDs hidden (R111)
- 15+ unit tests covering: `/status` format (pending approvals, recent runs, timezone display), `/agenda` format (timed events, all-day events, stub/no-credentials case), proactive notification dispatch

## Proof Level

- This slice proves: integration (formatter over real dict shapes + wiring into real worker path)
- Real runtime required: no (unit tests only; real Calendar API and real Telegram push verified in UAT)
- Human/UAT required: yes (operator verifies `/status`, `/agenda`, and proactive push via Telegram after deploy)

## Verification

- `OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c "from helm_telegram_bot.commands import status, agenda; print('imports ok')"`
- `grep -n "status.handle\|agenda.handle" apps/telegram-bot/src/helm_telegram_bot/main.py` → must show both handlers registered
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_status_command.py -v` → all pass
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_agenda_command.py -v` → all pass
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_worker_notification.py -v` → all pass
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py` → no regressions (485+ passed)

## Observability / Diagnostics

- Runtime signals: structlog `proactive_approval_notification_sent` (run_id, workflow_type) fired in worker when notification dispatched; `digest_delivered` already fired in `TelegramDigestDeliveryService.deliver()`
- Inspection surfaces: `grep "proactive_approval_notification_sent" <log-stream>` — confirms notification fired per weekly workflow approval; `/status` command output in Telegram — live operator-facing state
- Failure visibility: if `TelegramDigestDeliveryService.deliver()` fails (missing bot token), it raises `RuntimeError` — worker logs unhandled exception via structlog; if Calendar credentials missing, `/agenda` shows "Calendar not configured" message
- Redaction constraints: proposal summaries may contain task titles (user content); do not log full proposal text at INFO level; log `run_id` and `workflow_type` only

## Integration Closure

- Upstream surfaces consumed:
  - `TelegramWorkflowStatusService.list_runs_needing_action()` / `list_recent_runs()` (existing) → `/status` data source
  - `TelegramDigestDeliveryService.deliver(text)` (existing) → extended with `notify_approval_needed`
  - `workflow_runs.run()` in `apps/worker` → notification wired after `resume_runnable_runs()`
  - `WorkflowStatusService.get_run_detail(run_id)` → consulted in worker to check `needs_action` flag
  - `GoogleCalendarAdapter._get_service()` and `events().list()` → new `list_today_events` method
  - `settings.operator_timezone` (BotSettings via `get_settings()`) → timezone display in `/status` and `/agenda`
- New wiring introduced in this slice:
  - `commands/status.py` — new command, registered in `main.py`
  - `commands/agenda.py` — new command, registered in `main.py`
  - `TelegramDigestDeliveryService.notify_approval_needed(run_id, proposal_summary)` — new method
  - `workflow_runs.run()` extended with post-resume notification loop
- What remains before the milestone is truly usable end-to-end: S05 (E2E calendar tests), S06 (live reload + Datadog + cleanup)

## Tasks

- [x] **T01: Build `/status` command and `notify_approval_needed` delivery method** `est:45m`
  - Why: Closes R109 (operator-facing `/status`) and provides the delivery primitive needed by T03 for proactive notification. `/status` is the fastest-value deliverable — no new infrastructure, just formatting over existing service methods. `notify_approval_needed` is a simple extension of `TelegramDigestDeliveryService` and is logically grouped here since it's the same service tested by `/status` unit tests.
  - Files: `apps/telegram-bot/src/helm_telegram_bot/commands/status.py` (new), `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py`, `tests/unit/test_status_command.py` (new)
  - Do: See T01-PLAN.md
  - Verify: `pytest tests/unit/test_status_command.py -v` → all pass; `python -c "from helm_telegram_bot.commands import status; print('ok')"` → clean import
  - Done when: `/status` handler function exists with 5+ unit tests covering pending approvals format, recent completions format, empty state, and timezone display; `notify_approval_needed` method added to `TelegramDigestDeliveryService` with test

- [x] **T02: Add `list_today_events` to GoogleCalendarAdapter and build `/agenda` command** `est:45m`
  - Why: Closes R110 (`/agenda` shows today's calendar events in local time). `list_today_events` is the only net-new non-trivial code in S04 — it calls the Google Calendar API and must handle both timed and all-day event formats. The command is a thin formatter over this method.
  - Files: `packages/connectors/src/helm_connectors/google_calendar.py`, `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py` (new), `tests/unit/test_agenda_command.py` (new)
  - Do: See T02-PLAN.md
  - Verify: `pytest tests/unit/test_agenda_command.py -v` → all pass; `python -c "from helm_telegram_bot.commands import agenda; print('ok')"` → clean import
  - Done when: `GoogleCalendarAdapter.list_today_events(calendar_id)` exists and handles both `start.dateTime` and `start.date` event shapes; `/agenda` command handles stub/no-credentials gracefully; 5+ unit tests covering timed events, all-day events, empty calendar, and no-credentials case

- [x] **T03: Wire proactive notification into worker and register both new commands** `est:30m`
  - Why: Closes R108 (proactive approval notification), R111 (concise default output), and R102's remaining gap (timezone in `/status` output). This task wires the `notify_approval_needed` method from T01 into the worker's `run()` function so weekly workflow approval checkpoints push without polling. It also registers both new commands in `main.py` and adds the proactive notification unit tests.
  - Files: `apps/worker/src/helm_worker/jobs/workflow_runs.py`, `apps/telegram-bot/src/helm_telegram_bot/main.py`, `tests/unit/test_worker_notification.py` (new)
  - Do: See T03-PLAN.md
  - Verify: `pytest tests/unit/test_worker_notification.py -v` → all pass; `grep "status.handle\|agenda.handle" apps/telegram-bot/src/helm_telegram_bot/main.py` → both present; full suite no regressions
  - Done when: `workflow_runs.run()` calls `notify_approval_needed` for each newly-advanced `needs_action=True` run; both `/status` and `/agenda` registered in `main.py`; 4+ unit tests covering notification dispatch, deduplication safety, and no-notification when no runs need action

## Files Likely Touched

- `apps/telegram-bot/src/helm_telegram_bot/commands/status.py` (new)
- `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py` (new)
- `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py`
- `apps/telegram-bot/src/helm_telegram_bot/main.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `packages/connectors/src/helm_connectors/google_calendar.py`
- `tests/unit/test_status_command.py` (new)
- `tests/unit/test_agenda_command.py` (new)
- `tests/unit/test_worker_notification.py` (new)
