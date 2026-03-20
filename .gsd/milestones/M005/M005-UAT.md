# M005 UAT: Helm Telegram Surface

Covers the three demo flows that M005 must deliver end-to-end:
task scheduling, agenda, and email triage → approval → send.
Also covers log verification for each flow.

---

## Pre-flight Checklist

Run these before starting any flow. A failure here will block everything downstream.

### 1. Environment variables

```bash
# Required — verify all are set and non-empty
echo "TELEGRAM_ALLOWED_USER_ID: $TELEGRAM_ALLOWED_USER_ID"
echo "GOOGLE_CLIENT_ID:         $GOOGLE_CLIENT_ID"
echo "GOOGLE_CLIENT_SECRET:     $GOOGLE_CLIENT_SECRET"
echo "GOOGLE_REFRESH_TOKEN:     $GOOGLE_REFRESH_TOKEN"
echo "GOOGLE_USER_EMAIL:        $GOOGLE_USER_EMAIL"
echo "OPERATOR_TIMEZONE:        $OPERATOR_TIMEZONE"
echo "OPENAI_API_KEY:           $OPENAI_API_KEY"
echo "DATABASE_URL:             $DATABASE_URL"
echo "TELEGRAM_BOT_TOKEN:       $TELEGRAM_BOT_TOKEN"
```

Expected: all present, none empty.

### 2. Database bootstrap

```bash
bash scripts/migrate.sh
```

Expected log output (search for these events):

```
{"event": "bootstrap_user_seeded", "user_id": <N>, "telegram_user_id": "<YOUR_ID>", ...}
```

If you see `bootstrap_user_skipped` instead, `TELEGRAM_ALLOWED_USER_ID` is unset.

Verify DB state:

```sql
SELECT id, telegram_user_id, display_name, timezone FROM users;
SELECT provider, email, access_token IS NOT NULL AS has_token, expires_at FROM user_credentials;
```

Expected: 1 user row, 1 credential row with `provider='google'` and `email` set.
`access_token` may be NULL at this point — it gets written on the first real API call.

### 3. Stack startup

Start all three services in separate terminals:

```bash
# Terminal 1
bash scripts/run-api.sh

# Terminal 2
bash scripts/run-worker.sh

# Terminal 3
bash scripts/run-telegram-bot.sh
```

Expected log events on startup:

| Service | Event | Notes |
|---|---|---|
| worker | `worker_started` | Fields: `poll_seconds`, `jobs` list |
| bot | `telegram_bot_started` | |

If worker emits `worker_job_failed` immediately, check `DATABASE_URL` and Postgres connectivity.

---

## Flow 1: `/task` — Schedule a Task

### Steps

1. Open Telegram, send to your bot:
   ```
   /task book dentist appointment this week
   ```

2. Bot should reply within ~2 seconds:
   - Acknowledgement that the task was received
   - Either: "Task scheduled — event created on your calendar" (auto-approve path)
   - Or: an approval prompt with `/approve N M` (approval-required path)

3. If approval prompt: reply with the `/approve N M` command shown.

4. Bot should confirm calendar event created.

### Expected logs (worker terminal)

```
{"event": "calendar_provider_constructed", "user_id": 1, "source": "db_credentials", ...}
```

On the **first** `/task` call, also expect:

```
{"event": "google_credentials_refreshed", "user_id": 1, "expires_at": "...", ...}
```

This is the token refresh write-back. After this, `access_token` and `expires_at` will be
populated in `user_credentials`. Subsequent calls won't emit `google_credentials_refreshed`
until the token nears expiry.

Calendar write events (in worker or bot terminal):

```
{"event": "calendar_upsert_insert", "user_id": 1, "calendar_id": "primary", ...}
{"event": "calendar_upsert_success", "user_id": 1, "event_id": "<gcal_id>", "operation": "insert", ...}
```

If the task goes to approval first, then after `/approve`:

```
{"event": "calendar_provider_constructed", "user_id": 1, "source": "db_credentials", ...}
{"event": "calendar_upsert_insert", ...}
{"event": "calendar_upsert_success", ...}
```

### Pass criteria

- [ ] Bot acknowledged `/task` within ~2 seconds
- [ ] Calendar event appears in Google Calendar at the expected time in `OPERATOR_TIMEZONE`
- [ ] `calendar_upsert_success` in logs
- [ ] `google_credentials_refreshed` on first call only; absent on subsequent calls

### Failure diagnostics

| Symptom | Check |
|---|---|
| Bot doesn't reply | `TELEGRAM_BOT_TOKEN` and bot polling are up |
| "No Helm user found" reply | `TELEGRAM_ALLOWED_USER_ID` matches your Telegram user ID; `users` row exists |
| `RuntimeError: No Google credentials` in logs | `user_credentials` row exists with `provider='google'` |
| `google_credentials_refresh_failed` in logs | `GOOGLE_REFRESH_TOKEN` is stale — regenerate it |
| `calendar_upsert_failed` in logs | Check `status_code` field — 403 means wrong scopes, 401 means bad token |
| Event lands at wrong time | Check `OPERATOR_TIMEZONE` value; verify event `start.dateTime` in Google Calendar has the correct UTC offset |

---

## Flow 2: `/agenda` — List Today's Events

### Steps

1. Send to your bot:
   ```
   /agenda
   ```

2. Bot should reply with today's events from your Google Calendar, formatted as:
   ```
   📅 Today — Monday, March 18

   • 9:00 AM – 10:00 AM  Dentist appointment (1h)
   • 2:00 PM – 3:00 PM   Team sync (1h)
   ```
   Or: "No events scheduled for today." if your calendar is empty.

### Expected logs (bot terminal)

```
{"event": "list_today_events", "user_id": 1, "calendar_id": "primary", "timezone": "<OPERATOR_TIMEZONE>", ...}
{"event": "list_today_events_complete", "user_id": 1, "event_count": <N>, ...}
```

If `OPERATOR_TIMEZONE` is correct, `list_today_events` will show the right timezone field.

### Pass criteria

- [ ] Bot replies with event list (or "no events") within ~3 seconds
- [ ] Event times shown in `OPERATOR_TIMEZONE` (not UTC)
- [ ] `list_today_events_complete` in logs with correct `event_count`
- [ ] Event just created in Flow 1 appears in the list (if today)

### Failure diagnostics

| Symptom | Check |
|---|---|
| "No Helm user found for your Telegram account." | Same as Flow 1 — user row / `TELEGRAM_ALLOWED_USER_ID` |
| Empty list when events exist | Check `OPERATOR_TIMEZONE` — wrong timezone means the "today" window may not include your events |
| Times show as UTC | `OPERATOR_TIMEZONE` not being read; check env var and `setup_logging()` call in bot startup |
| `google_credentials_refresh_failed` | Same as Flow 1 |

---

## Flow 3: Email Triage → Approval → Send

> This flow requires email pipeline configuration (`GMAIL_*` vars, email agent config in DB).
> Skip if email pipeline is not configured for this environment.

### Steps

#### 3a. Trigger email triage

Either wait for the worker's scheduled email triage job (runs on its poll cycle), or trigger manually:

```bash
# Manual trigger via API (if endpoint is wired)
curl -X POST http://localhost:8000/internal/jobs/email_triage
```

Expected worker log:

```
{"event": "gmail_provider_constructed", "user_id": 1, "source": "db_credentials", ...}
{"event": "gmail_pull_completed", "user_id": 1, "count": <N>, "mode": "...", "next_history_cursor": "...", ...}
```

If `count` is 0, there are no new messages since the last cursor. That's fine — the triage
job is idempotent.

#### 3b. Receive triage notification

Bot should push a Telegram message with triage results — draft reply suggestions and
an approval prompt with `/approve N M`.

#### 3c. Approve a draft reply

Reply with:
```
/approve N M
```

Where `N` is the workflow run ID and `M` is the step index shown in the approval prompt.

#### 3d. Verify send

Expected logs:

```
{"event": "gmail_send_completed", "user_id": 1, "to_address": "<recipient>", "provider_message_id": "...", ...}
```

Check Gmail Sent folder — the reply should appear there.

### Pass criteria

- [ ] `gmail_pull_completed` in worker logs on triage cycle
- [ ] Triage notification pushed to Telegram (if new messages found)
- [ ] `/approve` triggers send; `gmail_send_completed` in logs
- [ ] Reply appears in Gmail Sent folder
- [ ] No `gmail_send_failed` events

### Failure diagnostics

| Symptom | Check |
|---|---|
| `gmail_pull_list_failed` | OAuth token issue — check `google_credentials_refresh_failed` nearby |
| `gmail_pull_message_failed` | Specific message ID failed to fetch — non-fatal; `failure_counts` shows how many |
| `gmail_history_bootstrap_poll` | First poll after bootstrap; cursor was NULL — this is expected, not an error |
| `gmail_send_failed` in logs | Check `error` field; 403 = scope issue (need `gmail.send`), 401 = token issue |
| No triage notification in Telegram | Check email agent config in DB; check `email_triage` job is not paused |

---

## Log Verification Reference

These are the key structured log events and what they confirm.

### Startup / Bootstrap

| Event | Level | Where | What it confirms |
|---|---|---|---|
| `bootstrap_user_seeded` | info | migrate.sh stdout | User + credentials row created/updated |
| `bootstrap_user_skipped` | warning | migrate.sh stdout | `TELEGRAM_ALLOWED_USER_ID` unset — bootstrap did nothing |
| `worker_started` | info | worker | Worker up; lists registered jobs |
| `telegram_bot_started` | info | bot | Bot polling active |

### Credential lifecycle

| Event | Level | Where | What it confirms |
|---|---|---|---|
| `google_credentials_refreshed` | info | worker/bot | Token refreshed; `expires_at` written to DB. Fields: `user_id`, `expires_at` |
| `google_credentials_refresh_failed` | error | worker/bot | Refresh token rejected. Fields: `user_id`, `error` (exception class name) |

This should appear **once** on first run after bootstrap, then only when token nears expiry (~hourly).
If it appears on every request, the token is not being persisted.

### Calendar (/task, /agenda)

| Event | Level | Where | What it confirms |
|---|---|---|---|
| `calendar_provider_constructed` | info | worker/bot | Provider built from DB credentials. Fields: `user_id`, `source="db_credentials"` |
| `calendar_upsert_insert` | info | worker/bot | New event insert attempt. Fields: `user_id`, `calendar_id`, `event_id` |
| `calendar_upsert_update` | info | worker/bot | Existing event update attempt |
| `calendar_upsert_success` | info | worker/bot | Calendar write confirmed. Fields: `user_id`, `event_id`, `operation`, `status_code` |
| `calendar_upsert_failed` | error | worker/bot | Calendar write failed. Fields: `user_id`, `status_code`, `retry_disposition` |
| `list_today_events` | info | bot | `/agenda` query started. Fields: `user_id`, `calendar_id`, `timezone` |
| `list_today_events_complete` | info | bot | `/agenda` query done. Fields: `user_id`, `event_count` |
| `reconcile_calendar_block_success` | info | worker | Drift check passed — event matches expected state |
| `reconcile_calendar_block_drift_detected` | info | worker | External edit detected on a scheduled block |
| `past_event_guard_triggered` | warning | worker | Scheduled slot is in the past; task carried forward |

### Gmail (email pipeline)

| Event | Level | Where | What it confirms |
|---|---|---|---|
| `gmail_provider_constructed` | info | worker | GmailProvider built from DB credentials. Fields: `user_id`, `source="db_credentials"` |
| `gmail_history_bootstrap_poll` | info | worker | First poll (cursor was NULL). Normal on first run |
| `gmail_pull_completed` | info | worker | Pull cycle done. Fields: `user_id`, `count`, `failure_counts`, `mode`, `next_history_cursor` |
| `gmail_pull_list_failed` | warning | worker | Failed to list changed message IDs. Fields: `error` |
| `gmail_pull_message_failed` | warning | worker | Failed to fetch one message. Fields: `message_id`, `error`. Non-fatal |
| `gmail_send_completed` | info | bot/worker | Reply sent. Fields: `user_id`, `to_address`, `provider_message_id`, `provider_thread_id` |
| `gmail_send_failed` | error | bot/worker | Send failed. Fields: `user_id`, `to_address`, `error` |

### Workflow / approval

| Event | Level | Where | What it confirms |
|---|---|---|---|
| `workflow_runs_job_processed` | info | worker | Poll cycle completed; `resumed_count` shows how many runs advanced |
| `proactive_approval_notification_sent` | info | worker | Approval push delivered to Telegram |
| `proactive_approval_notification_failed` | warning | worker | Push failed (Telegram API error or bad chat ID) |
| `task_execution_complete` | info | bot | Inline task execution finished |
| `task_execution_past_time` | warning | bot | Task time was in the past — user shown a message |
| `task_execution_failed` | error | bot | Unhandled exception during inline execution |

### What's not logged (by design)

- `access_token`, `refresh_token`, `client_secret` — never appear in any log event
- Full email body content — not logged
- Telegram message text — not logged (only command names and run IDs appear)

---

## Quick diagnostic commands

```bash
# Confirm provider imports are healthy
uv run python -c "from helm_providers import GoogleCalendarProvider, GmailProvider, CalendarProvider, InboxProvider; print('ok')"

# Confirm stub adapters are in place
uv run python -c "from helm_orchestration import StubCalendarSystemAdapter, StubTaskSystemAdapter; print('ok')"

# Confirm bootstrap symbols
uv run python -c "from helm_storage.repositories import get_credentials, get_user_by_telegram_id; print('ok')"

# Confirm no connector residue
uv run python -c "import helm_connectors" 2>&1  # should raise ModuleNotFoundError

# Run unit + integration suite
uv run pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py -q

# Check for any helm_connectors import leakage
rg "helm_connectors" apps/ packages/ tests/ --type py
```
