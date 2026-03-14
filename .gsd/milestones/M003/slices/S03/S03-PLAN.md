# S03: Telegram Real-Time Execution UX

**Goal:** Extend the Telegram workflow interface to display real-time sync execution events—calendar and task writes, drift detection, reconciliation—as they happen, not just completion summaries.

**Demo:** Running `/workflows <run_id>` shows not only the completion summary but also a timeline of recent sync events: each event displays task/calendar title, sync status, timestamp, and drift details if detected. A new `/workflow_sync_detail <run_id>` command shows the full sync event timeline for deep-dive inspection.

## Must-Haves

- Sync event query interface in WorkflowStatusService exposing sync records and events scoped to a workflow run
- Telegram formatter functions rendering sync records and drift events as concise, human-readable messages
- `/workflows` command extended to show sync event timeline alongside completion summary
- `/workflow_sync_detail <run_id>` command for full sync timeline inspection
- All existing workflow commands remain unchanged; backward compatibility verified

## Proof Level

- This slice proves: **operational** — Real-time sync progress visible in Telegram, failures and drift events clear, recovery options discoverable from Telegram status.
- Real runtime required: **yes** — Telegram messages must format correctly with real sync record data.
- Human/UAT required: **no** — Unit and integration tests sufficient; S05 UAT will exercise operator experience end-to-end.

## Verification

- `tests/unit/test_telegram_sync_formatters.py` — 8+ unit tests verifying sync record, drift event, and edge-case formatting (long titles, truncation, missing fields)
- `tests/integration/test_telegram_workflow_sync_commands.py` — 3+ integration tests verifying `/workflows` and `/workflow_sync_detail` command behavior with real sync data
- All existing tests remain green (zero regressions)
- Telegram message formatting matches constraints: max 4096 chars, graceful truncation for long timelines
- **Failure-path verification**: Tests confirm that edge cases (missing fields, malformed diffs, empty timelines) are handled without exceptions and logged appropriately; grep logs for "sync_timeline_formatted" to verify formatting signals present and truncation flags correct on timelines exceeding message size limits

## Observability / Diagnostics

- Runtime signals: Structured logs for sync query operations (count of records fetched, drift events found, formatters called)
- Inspection surfaces: Query database `SELECT * FROM workflow_sync_records WHERE workflow_run_id=X ORDER BY created_at DESC` to inspect raw sync state; grep logs for "sync_event_format" debug signals
- Failure visibility: Missing sync records (empty timeline), malformed event details (missing field_diffs), formatter exceptions (caught and logged with context)
- Redaction constraints: No sensitive payloads logged; field diffs are user-visible event properties (title, start, end) not credentials
- **Diagnostics Verification:** Test that empty/missing scenarios are handled gracefully: (1) Call `list_sync_events(run_id)` on a run with zero sync records — verify empty list returned with no exceptions; (2) Call `get_sync_details(run_id)` on a run with drift events but missing field_diffs — verify method returns dict with empty/null drift_events gracefully logged; (3) Inspect logs for "sync_query_executed" entries with counts and durations on successful queries (verify observability signals are present)

## Integration Closure

- Upstream surfaces consumed: `WorkflowStatusService.get_run_detail()` (existing), `WorkflowSyncRecordRepository.list_for_run()` (S02), `WorkflowEventRepository.list_for_run_by_type()` (S02), existing Telegram command handlers
- New wiring introduced: `TelegramWorkflowStatusService.list_sync_events()` and `get_sync_details()` methods; new formatter module with sync event and drift renderers; command handlers for `/workflow_sync_detail`
- What remains before end-to-end: S04 recovery policy (how Helm responds to drifts); S05 end-to-end workflow with operator presence

## Tasks

- [x] **T01: Sync Event Query Interface** `est:45m`
  - Why: Expose sync records and events from the database through the service layer so formatters have data to render
  - Files: `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`, `tests/unit/test_telegram_sync_queries.py`
  - Do: Add `list_sync_events(run_id: int) -> list[dict[str, object]]` and `get_sync_details(run_id: int) -> dict[str, object]` methods to `TelegramWorkflowStatusService`. Query sync records (via `WorkflowSyncRecordRepository.list_for_run()`) and drift events (via `WorkflowEventRepository.list_for_run_by_type('drift_detected_external_change')`). Return structured data ready for formatting: sync_records list with status/timestamp/external_object_id, drift_events list with field_diffs, sync counts (total/task/calendar). Reuse existing `_build_completion_summary()` logic from WorkflowStatusService to avoid count duplication. Handle edge cases: empty results, missing events, incomplete drift metadata.
  - Verify: `pytest tests/unit/test_telegram_sync_queries.py -v` all tests green; manually call `list_sync_events(run_id)` in a test and verify return structure matches expected dict schema
  - Done when: Methods return properly-typed dicts, all sync records and events are fetched correctly, zero errors on missing/incomplete data

- [x] **T02: Telegram Formatter Extensions** `est:50m`
  - Why: Transform sync records and drift events into human-readable Telegram messages so operators can see what's happening
  - Files: `apps/telegram-bot/src/helm_telegram_bot/formatters/sync_events.py` (new), `tests/unit/test_telegram_sync_formatters.py` (new)
  - Do: Create `sync_events.py` module with three formatter functions: (1) `format_sync_record(record: dict) -> str` — extracts title, status, timestamp, external_object_id, renders as single-line summary (e.g., "✓ Task X synced to task_system at 02:35:10"); (2) `format_drift_event(event: dict, sync_record: dict) -> str` — extracts field_diffs from event.details, compares before/after, renders human-readable drift summary (e.g., "Event Y rescheduled: start changed from 10:00 to 14:00"); (3) `format_sync_timeline(sync_events: list[dict], max_events: int = 8) -> str` — renders recent N sync events as newline-separated timeline, truncates gracefully if timeline exceeds Telegram message size, indicates "... and 5 more events" if truncated. All formatters handle edge cases defensively: missing keys use `.get()` with defaults, malformed diffs logged but don't crash, long titles truncated to 40 chars. Follow existing patterns in `workflows.py` (_format_run, _proposal_detail_lines) for consistency.
  - Verify: `pytest tests/unit/test_telegram_sync_formatters.py -v` tests cover: happy path (real sync record/event), missing fields, malformed diffs, truncation for long titles, message size limits, drift detection signal in output
  - Done when: All formatters produce valid Telegram markdown, edge cases handled without exceptions, output messages are under 4096 chars, field names and values render correctly

- [x] **T03: Integration into Workflow Commands** `est:45m`
  - Why: Wire the sync formatters into the existing Telegram workflow commands so operators see sync events when they check run status
  - Files: `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`, `tests/integration/test_telegram_workflow_sync_commands.py` (new)
  - Do: (1) Extend `_format_run()` function to optionally include sync timeline. Query sync events via `_service.list_sync_events(run['id'])`, format via `sync_events.format_sync_timeline()`, append to the existing output lines. Keep the extension conditional: only show timeline if sync records exist (no clutter for non-sync workflows). (2) Add new async command handler `async def sync_detail(update: Update, context: ContextTypes.DEFAULT_TYPE)` — parses `run_id` from args using existing `parse_single_id_arg()` pattern, calls `_service.get_sync_details(run_id)`, formats full timeline via formatter, replies with result. Use existing error handling pattern (check for None, reply with "Run not found" if needed). (3) Register the new command in the bot's command handlers. Update `/workflows` help text to mention new command. Verify backward compatibility: `/workflows` without args still works, `/workflows <run_id>` still shows completion summary, new sync timeline is appended below.
  - Verify: `pytest tests/integration/test_telegram_workflow_sync_commands.py -v` tests verify: `/workflows <run_id>` includes sync timeline when records exist, `/workflow_sync_detail <run_id>` returns full timeline, error handling for invalid/missing run_id, message content and format correct
  - Done when: Commands execute without error, Telegram message format is valid, existing tests still pass (zero regressions), new functionality integrated seamlessly into existing command structure

## Files Likely Touched

- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — Add sync query methods
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` — Extend _format_run, add sync_detail command
- `apps/telegram-bot/src/helm_telegram_bot/formatters/sync_events.py` — New formatter module
- `tests/unit/test_telegram_sync_queries.py` — New unit tests for sync query methods
- `tests/unit/test_telegram_sync_formatters.py` — New unit tests for formatter functions
- `tests/integration/test_telegram_workflow_sync_commands.py` — New integration tests for commands
