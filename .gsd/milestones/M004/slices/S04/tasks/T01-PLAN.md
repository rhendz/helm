---
estimated_steps: 7
estimated_files: 3
---

# T01: Build `/status` command and `notify_approval_needed` delivery method

**Slice:** S04 — Telegram UX Overhaul and Proactive Notifications
**Milestone:** M004

## Description

Create the `/status` command as a new `commands/status.py` file. It queries `TelegramWorkflowStatusService.list_runs_needing_action()` and `list_recent_runs()` (both already exist) and formats a concise operator-facing response: pending approvals with `/approve N M` hints, recent completions (last 5), and the active `OPERATOR_TIMEZONE`. No `current_step`, `paused_state`, sync metadata, or run IDs in default output (D008).

Also add `notify_approval_needed(run_id: int, proposal_summary: str)` to `TelegramDigestDeliveryService`. This method formats a "⏳ Schedule proposal ready" message and calls `self.deliver(text)`. T03 will call this from the worker — this task only adds the method and tests it in isolation.

The new command is **not** registered in `main.py` in this task — T03 handles all registration so there is a single registration diff.

## Steps

1. **Create `apps/telegram-bot/src/helm_telegram_bot/commands/status.py`**
   - Auth guard via `reject_if_unauthorized(update, context)` — import from `commands.common`
   - Call `_service.list_runs_needing_action(limit=5)` and `_service.list_recent_runs(limit=5)`
   - Read timezone from `get_settings().operator_timezone`
   - Format output (see format in S04-RESEARCH.md):
     - Header: `📋 Helm Status\nTimezone: <tz>`
     - Pending approvals section: for each run where `needs_action=True`, show `• Run N — <proposal_summary>\n  /approve N M to confirm` using `run["approval_checkpoint"]["target_artifact_id"]` and `run["approval_checkpoint"]["proposal_summary"]`
     - Recent completions section: for each completed run, show `• <workflow_type_label> — <headline>` where headline comes from `run["completion_summary"]["headline"]` if present, else `run.get("last_event_summary", "completed")`
     - If no pending approvals: `✅ No pending approvals.`
     - If no recent completions: `No recent activity.`
   - `_service = TelegramWorkflowStatusService()` at module level
   - `async def handle(update, context)` is the entry point

2. **Add `notify_approval_needed` to `TelegramDigestDeliveryService`**
   - In `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py`
   - Method signature: `def notify_approval_needed(self, run_id: int, proposal_summary: str) -> None`
   - Formats message: `f"⏳ Schedule proposal ready (run {run_id})\n{proposal_summary}\nUse /approve {run_id} <artifact_id> to confirm or /reject {run_id} <artifact_id> to decline."`
   - Calls `self.deliver(text)` — reuses existing delivery path (asyncio.run inside deliver is safe from sync context)
   - Add structlog log line: `logger.info("proactive_approval_notification_sent", run_id=run_id)`

3. **Create `tests/unit/test_status_command.py`**
   - Mirror the `_Message` / `_Update` / `_Context` pattern from `tests/unit/test_workflow_telegram_commands.py`
   - Add `_Service` stub class with `list_runs_needing_action` and `list_recent_runs` methods
   - Mock `status._service` via `monkeypatch.setattr(status, "_service", _Service(...))`
   - Mock `status.get_settings()` to return a settings stub with `operator_timezone = "America/Los_Angeles"`
   - Test 1: `test_status_no_pending_approvals_no_recent` — both lists empty → shows "No pending approvals" and "No recent activity"
   - Test 2: `test_status_shows_pending_approval_with_approve_hint` — one run with `needs_action=True`, `approval_checkpoint={"target_artifact_id": 42, "proposal_summary": "Schedule: dentist"}` → reply contains `/approve 7 42`
   - Test 3: `test_status_shows_recent_completions` — one completed run with `completion_summary={"headline": "Scheduled 3 blocks"}` → reply contains "Scheduled 3 blocks"
   - Test 4: `test_status_shows_operator_timezone` — reply contains "America/Los_Angeles"
   - Test 5: `test_status_no_debug_internals` — reply does NOT contain "current_step", "paused_state", "sync"
   - Test 6: `test_notify_approval_needed_calls_deliver` — patches `TelegramDigestDeliveryService.deliver`, calls `notify_approval_needed(run_id=7, proposal_summary="Schedule: dentist")`, asserts `deliver` called with text containing "run 7" and "/approve 7"

## Must-Haves

- [ ] `/status` handler is async, has auth guard, reads from `list_runs_needing_action` and `list_recent_runs`
- [ ] `/status` output includes OPERATOR_TIMEZONE, pending approvals with `/approve N M` hint, and recent completions
- [ ] `/status` output never contains `current_step`, `paused_state`, `sync`, or raw run IDs in non-approval context (D008)
- [ ] `notify_approval_needed` added to `TelegramDigestDeliveryService`, calls `self.deliver()`, logs `proactive_approval_notification_sent`
- [ ] 6 unit tests in `test_status_command.py`, all passing

## Verification

```bash
OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c \
  "from helm_telegram_bot.commands import status; print('import ok')"
# → import ok

OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c \
  "from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService; \
   import inspect; assert 'notify_approval_needed' in dir(TelegramDigestDeliveryService); print('method ok')"

OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_status_command.py -v
# → 6 passed
```

## Observability Impact

- Signals added/changed: `proactive_approval_notification_sent` INFO structlog event added to `TelegramDigestDeliveryService.notify_approval_needed` (run_id field)
- How a future agent inspects this: `grep "proactive_approval_notification_sent" <log-stream>` — each line confirms a notification was sent with its run_id
- Failure state exposed: if `deliver()` raises (missing bot token), the exception propagates to the caller (worker) where it will be caught and logged

## Inputs

- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — `list_runs_needing_action()` and `list_recent_runs()` are already implemented; read the existing return shapes before writing the formatter. The run dict contains `id`, `needs_action`, `workflow_type`, `approval_checkpoint` (dict with `target_artifact_id`, `proposal_summary`), `completion_summary` (dict with `headline`, or `None` for `task_quick_add` runs), `last_event_summary`.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` — reference for `_service` module-level pattern, auth guard usage, `_send_paginated` helper, and `_Message`/`_Update`/`_Context` test stub patterns. Do NOT modify this file.
- `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` — existing `deliver(text)` method uses `asyncio.run()`; `notify_approval_needed` must call this, not create a new asyncio loop.
- S03 Forward Intelligence: `approval_checkpoint` key in run dict contains `target_artifact_id` and `proposal_summary`; `completion_summary` is `None` for `task_quick_add` runs, present for `weekly_scheduling` runs.

## Expected Output

- `apps/telegram-bot/src/helm_telegram_bot/commands/status.py` — new file with `handle(update, context)` async function, concise formatter, auth guard, module-level `_service`
- `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` — `notify_approval_needed(run_id, proposal_summary)` method added
- `tests/unit/test_status_command.py` — new file with 6 passing unit tests
