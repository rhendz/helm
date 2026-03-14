# S05: End-to-End Integration Verification and UAT

**Milestone:** M003 — Task/Calendar Productionization  
**Audience:** System Operator  
**Objective:** Verify that Helm's complete workflow (Google Calendar integration, drift detection, recovery actions, and Telegram visibility) works end-to-end in a live environment with real Calendar credentials and Telegram bot.

---

## UAT Type

**Hybrid mode**: automated integration tests (S01–S04) + operator-runnable test cases below.

- **Automated tests** exercise the full workflow in-memory with mocked external systems, proving correctness of Calendar auth, drift detection, recovery classification, and Telegram formatting. All hermetic; no external service dependencies.
- **Operator UAT** covers the same scenarios in your own environment with real Google Calendar credentials, live Telegram bot, and manual operator actions (e.g., manually rescheduling Calendar events to simulate drift).

**Why this mode is sufficient:**
- Integration tests validate data flow, state transitions, and durable persistence without requiring external services.
- UAT validates operator experience and real-world environment configuration (credential setup, service startup, command execution).
- Together: complete proof that the system works both technically (tests) and operationally (UAT).

---

## Prerequisites

**Time estimate:** 20–30 minutes total setup + 15 minutes per test case (60–90 minutes for full UAT).

### Environment Setup

1. **Check that Helm services can start:**
   - Python 3.11+, Node.js 18+ (if using TypeScript frontend)
   - SQLite (test database) or PostgreSQL (production database)
   - Git repo fully cloned with all dependencies installed
   - Run `pip install -r requirements.txt` and `pip install -e .` in repo root

2. **Google Cloud project with Calendar API enabled:**
   - Navigate to Google Cloud Console
   - Create or select a project
   - Enable **Google Calendar API**
   - Create OAuth 2.0 credentials (Desktop application or Web application)
   - Save `client_id` and `client_secret`
   - Obtain a `refresh_token` by running the OAuth flow (see Step 1 of each test case below)

3. **Telegram bot configured:**
   - Get your bot token from BotFather (`@BotFather` on Telegram)
   - Add your bot token to environment: `export TELEGRAM_BOT_TOKEN=<your-token>`
   - Save your Telegram user ID (e.g., chat ID from `/start` message or info menu)
   - Add to environment: `export TELEGRAM_USER_ID=<your-user-id>`

4. **Database access:**
   - `psql` client installed (for PostgreSQL) or sqlite3 client (for SQLite)
   - Know your database connection string or path
   - Test with: `psql -U <user> -h localhost <db_name> -c "SELECT 1"`

5. **Helm services running:**
   - API server: `python -m uvicorn apps.api.src.helm_api.main:app --reload --port 8000`
   - Worker: `python -m helm_worker.main` (in separate terminal)
   - Both should log startup messages without errors

---

## Test Case 1: Detect Manual Calendar Reschedule (Drift Detection)

**Objective:** Operator creates a workflow, approves it, Helm writes to Calendar, operator manually reschedules the event, Helm detects the change.

**Time estimate:** 15–20 minutes.

### Setup

1. **Set environment variables:**
   ```bash
   export CALENDAR_CLIENT_ID="<your-client-id>"
   export CALENDAR_CLIENT_SECRET="<your-client-secret>"
   export CALENDAR_REFRESH_TOKEN="<your-refresh-token>"
   export TELEGRAM_BOT_TOKEN="<your-bot-token>"
   ```
   
   If you don't have a refresh token yet, run this once:
   ```bash
   python scripts/get_calendar_credentials.py
   # Follow the browser OAuth flow, save the refresh_token
   ```

2. **Start Helm API (Terminal 1):**
   ```bash
   cd /Users/ankush/git/helm
   python -m uvicorn apps.api.src.helm_api.main:app --reload --port 8000
   # Expected output: "Application startup complete"
   ```

3. **Start Helm worker (Terminal 2):**
   ```bash
   cd /Users/ankush/git/helm
   python -m helm_worker.main
   # Expected output: "Worker started, listening for jobs"
   ```

4. **Test Telegram bot connectivity:**
   - Send `/start` to your Telegram bot
   - Bot should respond with welcome message
   - If no response, check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_USER_ID`

### Steps

1. **Create a workflow via API:**
   ```bash
   curl -X POST http://localhost:8000/v1/workflow-runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow_type": "weekly_scheduling",
       "first_step_name": "dispatch_task_agent",
       "request_text": "Schedule a weekly team sync for Monday 10 AM for 1 hour and a 1:1 review meeting for Tuesday 2 PM for 30 minutes",
       "submitted_by": "test-operator",
       "channel": "api"
     }'
   ```
   - Response includes `id` (the workflow_run_id)
   - Note this ID for subsequent commands

   **OR via Telegram** (if a bot command exists):
   ```
   Send: /workflow_start
   
   Request: "Schedule a weekly team sync for Monday 10 AM for 1 hour and a 1:1 review meeting for Tuesday 2 PM for 30 minutes"
   ```
   - Bot responds with a proposal showing 2 calendar blocks
   - Note the `workflow_run_id` from the bot response

2. **Approve the proposal:**
   ```bash
   curl -X POST http://localhost:8000/v1/workflow-runs/<run_id>/approve \
     -H "Content-Type: application/json" \
     -d '{"decision": "approved", "decision_actor": "test-operator"}'
   ```
   - Response confirms approval
   
   **OR via Telegram:**
   - Send: `/approve <run_id>` to the bot
   - Bot confirms: "Proposal approved, syncing to Calendar..."

3. **Wait for sync to complete (30–60 seconds):**
   - Bot sends updates as sync progresses
   - Check your Google Calendar (web or mobile app)
   - Verify: "Team Sync" event appears Monday 10 AM, "1:1 Review" appears Tuesday 2 PM

4. **Manually reschedule one event to simulate drift:**
   - In Google Calendar, open the "Team Sync" event
   - Change the time to **Monday 2 PM** (different from the 10 AM Helm proposed)
   - Save the change
   - Verify Calendar shows the new time

5. **Wait for drift detection (reconciliation happens automatically):**
   - Drift detection runs on a polling interval (60 seconds by default)
   - During the weekly scheduling workflow, the worker will periodically check for drifted events
   - Wait up to 90 seconds after the manual Calendar edit for Helm to detect it
   - Monitor worker logs for `drift_detected` signal:
   ```bash
   grep "drift_detected" logs/worker.log
   ```

6. **Check drift detection in Telegram:**
   ```
   Send: /workflows <run_id>
   ```
   - Bot output should show:
     - Sync timeline with status symbols (✓ = success, ⚠ = drift detected)
     - Drift event details showing: "External event was manually edited after Helm wrote it"
     - Field diffs: old time (10 AM) → new time (2 PM)
     - Recovery action: "request_replay" button/command

### SQL Verification

Open a database client and run:

```sql
-- Find the workflow run
SELECT id, workflow_type, status FROM workflow_runs 
WHERE id = '<run_id>' LIMIT 1;

-- Check sync records for drift
SELECT id, status, recovery_classification, external_object_id 
FROM workflow_sync_records 
WHERE run_id = '<run_id>' AND status = 'drift_detected';

-- Check drift events for details
SELECT event_type, details FROM workflow_events 
WHERE run_id = '<run_id>' AND event_type = 'drift_detected_external_change';
```

**Expected results:**
- First query: 1 row with status = `completed_with_drift` or `terminated_with_drift`
- Second query: 1 row with `recovery_classification = 'terminal_failure'`
- Third query: 1 row with details JSON containing `field_diffs` with before/after times

### Success Criteria

- [ ] Drift is detected within 90 seconds of manual Calendar edit
- [ ] Sync record marked `DRIFT_DETECTED` with `recovery_classification = TERMINAL_FAILURE`
- [ ] Drift event created with `field_diffs` showing time change
- [ ] Telegram `/workflows` command shows recovery action (`request_replay`)
- [ ] SQL queries return expected results
- [ ] No errors in API or worker logs

---

## Test Case 2: Verify Recovery Action Appears in Telegram

**Objective:** After drift is detected, operator sees the recovery action and can inspect what happened.

**Time estimate:** 5–10 minutes (builds on Test Case 1).

### Steps

1. **Query workflow status:**
   ```
   Send: /workflows <run_id>
   ```
   (Same `run_id` from Test Case 1)

2. **Observe the output:**
   - Status line shows: `COMPLETED_WITH_DRIFT` or similar
   - Sync timeline section shows 2 events:
     - ✓ "1:1 Review" (Monday sync) — succeeded
     - ⚠ "Team Sync" (Tuesday sync) — drift detected
   - Recovery actions section shows button/command: `request_replay`
   - Field diffs visible: `Monday 10:00 AM → Monday 2:00 PM`

3. **Get detailed sync timeline:**
   ```
   Send: /workflow_sync_detail <run_id>
   ```
   - Output shows all sync events (success, drift, reconciliation)
   - Each event timestamped and ordered
   - Drift event includes full `field_diffs` with field names, before values, after values

### Success Criteria

- [ ] Telegram `/workflows` command returns without error
- [ ] Response includes `safe_next_actions` with `request_replay` action
- [ ] Recovery action description is clear (e.g., "Replay this workflow to recover from manual Calendar edit")
- [ ] Sync timeline readable and shows drift status
- [ ] `/workflow_sync_detail` returns complete history without truncation

---

## Test Case 3: Operator Initiates Replay and Recovers

**Objective:** Operator requests replay, new sync lineage is created, workflow succeeds.

**Time estimate:** 10–15 minutes (builds on Test Case 2).

### Prerequisites

- Complete Test Case 1 and 2
- Manually fix the Calendar event before starting:
  - Open Google Calendar
  - Move "Team Sync" event back to **Monday 10 AM** (restore Helm's intent)
  - Save the change
  - This ensures reconciliation will succeed (no continued drift)

### Steps

1. **Initiate replay:**
   ```bash
   curl -X POST http://localhost:8000/v1/replay/workflow-runs/<run_id> \
     -H "Content-Type: application/json" \
     -d '{"actor": "test-operator"}'
   ```
   (Use the `run_id` from Test Cases 1–2)
   - Response confirms: "Replay requested, new sync lineage created"
   
   **OR via Telegram:**
   - Send: `/workflow_replay <run_id>` to the bot
   - Bot confirms: "Replay requested, new sync lineage created, processing..."

2. **Wait for replay to execute (30–60 seconds):**
   - Monitor bot for status updates
   - Check Telegram for "Replay completed" message

3. **Check final workflow status:**
   ```
   Send: /workflows <run_id>
   ```
   - Expected output:
     - Status: `COMPLETED` (successful after replay)
     - Sync timeline shows both lineages:
       - `[Gen 0]` (drift) ⚠ "Team Sync" — `drift_detected`
       - `[Gen 1]` (replay) ✓ "Team Sync" — `succeeded`
     - All events in time order

### SQL Verification

```sql
-- Check sync records and their lineages
SELECT id, status, lineage_generation, external_object_id, created_at
FROM workflow_sync_records 
WHERE run_id = '<run_id>' 
ORDER BY created_at;

-- Count by generation (should be 2: gen 0 and gen 1)
SELECT lineage_generation, COUNT(*) as count
FROM workflow_sync_records 
WHERE run_id = '<run_id>'
GROUP BY lineage_generation;

-- Expected: 
--   lineage_generation 0: original sync records (some may be drift_detected)
--   lineage_generation 1: replay sync records (should be succeeded)
```

**Expected results:**
- Multiple sync records visible (at least 2 per event, one per generation)
- Generation 0 includes `drift_detected` status
- Generation 1 includes `succeeded` status
- All records have same `external_object_id` (same Calendar event)

### Success Criteria

- [ ] Replay initiated without errors
- [ ] New sync records created with `lineage_generation = 1`
- [ ] Original drift records preserved with `lineage_generation = 0`
- [ ] Final workflow status shows `COMPLETED`
- [ ] Telegram output shows both generations (drift + replay) in timeline
- [ ] No silent data loss or record overwrites

---

## Test Case 4: Partial Failure Handling with Mixed Outcomes (Optional, Advanced)

**Objective:** Workflow with multiple syncs shows mixed outcomes (some succeed, some fail, some drift); counts are accurate and no data is silently lost.

**Time estimate:** 15–20 minutes (optional).

### Steps

1. **Create a larger workflow:**
   ```bash
   curl -X POST http://localhost:8000/v1/workflow-runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow_type": "weekly_scheduling",
       "first_step_name": "dispatch_task_agent",
       "request_text": "Schedule team standup Monday 9 AM, 1:1 Tuesday 2 PM, planning session Wednesday 3 PM, and add tasks: review design doc, write quarterly summary",
       "submitted_by": "test-operator",
       "channel": "api"
     }'
   ```
   - Response shows run_id
   - Proposal shows 3 calendar blocks + 2 tasks

2. **Approve the proposal:**
   ```
   Send: /approve <run_id>
   ```
   - Workflow starts syncing

3. **Introduce mixed outcomes (while sync is executing):**
   - **Success path:** Let task syncs complete normally
   - **Drift path:** Manually reschedule one Calendar event (e.g., move standup to 10 AM)
   - **Failure path (optional):** If possible, temporarily disconnect Calendar API to simulate failure; restore after 30 seconds

4. **Let workflow complete or terminate:**
   - Monitor Telegram for completion message
   - Workflow should show partial success with mixed counts

5. **Check final status:**
   ```
   Send: /workflows <run_id>
   ```
   - Output shows completion summary with counts:
     - "2 Calendar events synced (1 succeeded, 1 drifted)"
     - "2 tasks synced successfully"
     - Recovery action: "request_replay" for drifted event

### SQL Verification

```sql
-- Check all sync records
SELECT status, COUNT(*) as count
FROM workflow_sync_records 
WHERE run_id = '<run_id>'
GROUP BY status;

-- Example output:
-- status          | count
-- ----------------+-------
-- succeeded       |     2
-- drift_detected  |     1
-- cancelled       |     0
-- failed_terminal |     0

-- Verify counts by target system
SELECT target_system, COUNT(*) as count
FROM workflow_sync_records 
WHERE run_id = '<run_id>'
GROUP BY target_system;

-- Verify partial completion artifact
SELECT artifact_type, data 
FROM workflow_artifacts 
WHERE run_id = '<run_id>' AND artifact_type = 'completion_summary';
```

**Expected results:**
- Sync record counts match workflow status projection counts
- All records durable and queryable
- No silent drops or overwrites
- Completion summary artifact accurate

### Success Criteria

- [ ] Workflow terminates cleanly after partial success/failure
- [ ] Sync record counts match completion summary
- [ ] Mixed outcomes captured (success, drift, failure, cancelled)
- [ ] Recovery actions appropriate for each outcome
- [ ] SQL queries return expected counts
- [ ] No data loss or corruption

---

## Troubleshooting

### Auth Errors (401/403 from Google Calendar)

**Symptom:** Helm logs show `calendar_credential_refresh_failed` or API returns 401.

**Diagnosis:**
```bash
# Check refresh token validity
curl https://www.googleapis.com/oauth2/v1/tokeninfo?refresh_token=<refresh_token>
# If error, token is invalid or revoked
```

**Resolution:**
- Regenerate refresh token by running: `python scripts/get_calendar_credentials.py`
- Follow OAuth flow again in browser
- Update `CALENDAR_REFRESH_TOKEN` environment variable
- Restart Helm API and worker

### Calendar API Quota Exceeded (429 Errors)

**Symptom:** Helm logs show "429 rate_limit_exceeded" or API returns 429.

**Diagnosis:**
- Check your Google Cloud Console > APIs & Services > Quotas
- Look for Calendar API daily/per-minute quotas
- May be due to excessive reconciliation polling or test runs

**Resolution:**
- Wait for quota to reset (typically 1 hour for per-minute quota)
- Use a separate test calendar for UAT to avoid quota conflicts
- If problem persists, check quota limits and request increase in Google Cloud Console

### Drift Not Detected (Polling Delay)

**Symptom:** Manually rescheduled Calendar event not detected after 5 minutes.

**Diagnosis:**
- **Expected behavior**: Polling interval is 60 seconds
- Check logs for `drift_detected` signal with `grep "drift_detected" logs/app.log`
- May still be in polling interval window

**Resolution:**
- Wait up to 90 seconds total after manual Calendar edit
- Manually trigger reconciliation via API: `curl -X POST http://localhost:8000/api/runs/<run_id>/reconcile_sync`
- Check logs for drift signals; if still missing, check that Calendar API is returning live event state

### Telegram Bot Offline

**Symptom:** Telegram commands hang, no response, or "bot not responding" error.

**Diagnosis:**
- Check bot token: `env | grep TELEGRAM_BOT_TOKEN`
- Check connectivity: `curl -s https://api.telegram.org/bot<TOKEN>/getMe`
- If error, token is invalid or revoked

**Resolution:**
- Regenerate bot token from BotFather (`@BotFather` on Telegram)
- Update `TELEGRAM_BOT_TOKEN` environment variable
- Restart Helm worker and bot integration
- Verify connectivity again: `curl -s https://api.telegram.org/bot<TOKEN>/getMe | jq .ok` (should return `true`)

### Database Connection Errors

**Symptom:** SQL queries fail with "connection refused" or "database does not exist".

**Diagnosis:**
- Check database is running: `psql -U <user> -h localhost postgres -c "SELECT 1"`
- Check database name and user permissions
- Check connection string in environment or config

**Resolution:**
- Start database service: `systemctl start postgresql` (Linux) or `brew services start postgresql` (macOS)
- Verify credentials: `psql -U <user> -h localhost -W` (will prompt for password)
- Create test database if needed: `createdb <db_name>`
- Update connection string in Helm config or environment

### Test Database Appears Empty

**Symptom:** SQL queries return no rows; workflow runs not showing up.

**Diagnosis:**
- API or worker may not have initialized tables
- Wrong database selected

**Resolution:**
- Run migrations: `python -m alembic upgrade head`
- Verify tables exist: `\dt` in psql or `sqlite3 <db_path> ".tables"`
- Check that API and worker are writing to the same database

---

## UAT Success Criteria

### Checklist

- [ ] **Test Case 1 passes**: Drift detected on manual Calendar edit; sync record marked `DRIFT_DETECTED`; recovery_classification = `TERMINAL_FAILURE`
- [ ] **Test Case 2 passes**: Recovery action visible in Telegram `/workflows` output; operator can inspect sync timeline
- [ ] **Test Case 3 passes**: Replay initiated successfully; new lineage created; original drift preserved; workflow completes
- [ ] **Test Case 4 passes (optional)**: Partial failure counts accurate; mixed outcomes handled safely; no data loss
- [ ] **All SQL queries pass**: Queries run without syntax errors and return expected results
- [ ] **All Telegram commands work**: `/schedule`, `/approve`, `/workflows`, `/workflow_sync_detail`, `/request_replay` all execute without errors
- [ ] **Logs show expected signals**:
  - `calendar_auth_initialized` — Calendar auth works
  - `drift_detected` — Drift detection works
  - `sync_query_executed` — Sync queries execute
  - `sync_timeline_formatted` — Telegram formatting works
- [ ] **No silent data loss or corruption**: All state transitions auditable via SQL; no overwrites or missing records

### Failure Resolution

If any check fails:
1. **Record the failure**: Note test case, step, expected outcome, actual outcome
2. **Collect diagnostics**:
   - Relevant sync record ID(s) from workflow run
   - Error messages from Helm logs or Telegram
   - SQL query results (if applicable)
   - Full curl/API response (if applicable)
3. **Consult logs**:
   - API logs: `tail -f logs/api.log | grep <error_keyword>`
   - Worker logs: `tail -f logs/worker.log | grep <error_keyword>`
   - Database state: Run SQL queries from the test case verification section
4. **Report**: Include failure description, diagnostics, and logs in a summary

---

## Logging and Diagnostics

### Inspecting Application Logs

```bash
# All API logs
tail -f logs/api.log

# All worker logs
tail -f logs/worker.log

# Search for specific signals
grep "drift_detected" logs/*.log
grep "calendar_auth" logs/*.log
grep "sync_record" logs/*.log | grep -i "drift\|failure"

# Live tailing with filter
tail -f logs/api.log logs/worker.log | grep "drift_detected\|error\|warning"
```

### Inspecting Database State

```sql
-- All workflow runs
SELECT id, workflow_type, status, submitted_by, created_at 
FROM workflow_runs 
ORDER BY created_at DESC 
LIMIT 5;

-- Sync records for a specific run
SELECT id, status, target_system, recovery_classification, external_object_id, created_at 
FROM workflow_sync_records 
WHERE run_id = '<run_id>' 
ORDER BY created_at;

-- Workflow events (all types)
SELECT event_type, created_at, details 
FROM workflow_events 
WHERE run_id = '<run_id>' 
ORDER BY created_at;

-- Field diffs extraction (from drift events)
SELECT details->'field_diffs' as field_diffs 
FROM workflow_events 
WHERE run_id = '<run_id>' AND event_type = 'drift_detected_external_change';
```

---

## Notes for Tester

- **Running all tests**: Complete Test Cases 1–3 for full proof. Test Case 4 is optional and stress-tests mixed outcomes.
- **Credential refresh**: Refresh tokens may expire after 6 months of non-use. If you see 401 errors weeks later, regenerate credentials.
- **Polling latency**: Drift detection uses 60-second polling, not webhooks. This is intentional (simpler, less quota). Plan test timing around this delay.
- **Message truncation**: Telegram messages are limited to 4096 characters. Sync timelines with 8+ events may be truncated in `/workflows` output; use `/workflow_sync_detail` for full timeline.
- **Calendar API quota**: Personal Google accounts have a daily quota of ~1 million Calendar API requests. Normal UAT should use <10 requests per run. Heavy testing with many runs may approach quota; use a separate test calendar if needed.
- **Hermetic tests vs UAT**: Integration tests (S01–S04) run in-memory and are fully deterministic. This UAT requires real environment (credentials, services, Calendar). Expect minor timing variations and network latency.

---

## Appendix: SQL Query Reference

### Finding a Workflow Run

```sql
SELECT id, workflow_type, status, created_at 
FROM workflow_runs 
ORDER BY created_at DESC 
LIMIT 1;
-- Use the 'id' value as <run_id> in subsequent queries
```

### Querying Sync Records

```sql
-- All syncs for a run
SELECT id, status, planned_item_key, target_system, external_object_id, created_at 
FROM workflow_sync_records 
WHERE run_id = '<run_id>';

-- Only drift-detected syncs
SELECT id, status, recovery_classification 
FROM workflow_sync_records 
WHERE run_id = '<run_id>' AND status = 'drift_detected';

-- By lineage generation
SELECT lineage_generation, status, COUNT(*) as count 
FROM workflow_sync_records 
WHERE run_id = '<run_id>' 
GROUP BY lineage_generation, status;
```

### Querying Workflow Events

```sql
-- All events for a run
SELECT event_type, details, created_at 
FROM workflow_events 
WHERE run_id = '<run_id>' 
ORDER BY created_at;

-- Drift events only
SELECT event_type, details->'field_diffs' as field_diffs, created_at 
FROM workflow_events 
WHERE run_id = '<run_id>' AND event_type = 'drift_detected_external_change';
```

---

## References

- **DECISIONS.md**: Auth model, polling strategy, recovery policy: `.gsd/DECISIONS.md`
- **Integration tests**: S01–S04 test files in `tests/integration/test_weekly_scheduling_with_drift_recovery.py`
- **API endpoints**: `/v1/workflow-runs` (POST), `/v1/workflow-runs/<run_id>/approve` (POST), `/v1/replay/workflow-runs/<run_id>` (POST)
- **Telegram commands**: `/workflow_start`, `/approve`, `/workflows`, `/workflow_sync_detail`, `/workflow_replay` in `apps/telegram-bot`
- **Requirements mapping**: `REQUIREMENTS.md` (R006, R010, R011, R012, R013)
