---
estimated_steps: 9
estimated_files: 2
---

# T02: Telegram Formatter Extensions

**Slice:** S03 — Telegram Real-Time Execution UX
**Milestone:** M003

## Description

Create formatter functions to transform sync records and drift events into human-readable Telegram messages. Formatters handle edge cases (missing fields, long titles, message size limits) defensively and follow existing code patterns from `workflows.py`.

## Steps

1. Create new file `apps/telegram-bot/src/helm_telegram_bot/formatters/sync_events.py`
2. Implement `format_sync_record(record: dict[str, object]) -> str`:
   - Extract: title (from planned_item_key), status, external_object_id, created_at
   - Use status symbols: "✓" for SUCCEEDED, "⚠" for DRIFT_DETECTED, "✗" for FAILED, "⏳" for others
   - Format as single line: e.g., "✓ Task: Weekly meeting (evt_123abc) synced at 02:35:10"
   - Handle missing title gracefully (use planned_item_key fallback)
   - Truncate long titles to 40 chars to keep message compact
3. Implement `format_drift_event(event: dict[str, object], sync_record: dict[str, object]) -> str`:
   - Extract field_diffs from event['details'] (format: {"field_name": {"before": value, "after": value}})
   - Build human-readable diff lines: "start changed from 10:00 to 14:00"
   - Include planned_item_key as context
   - Format as multi-line block (compact but clear about what changed)
   - Use `.get()` with defaults for all nested field access (defensive)
4. Implement `format_sync_timeline(sync_records: list[dict], drift_events: dict, max_events: int = 8) -> str`:
   - Takes sync_records (from T01) and drift_events (keyed by sync_record_id for fast lookup)
   - Renders timeline of most recent max_events sync records
   - For each record, call `format_sync_record()` and append any associated drift event from `format_drift_event()`
   - Join lines with newlines
   - Check total message length; if exceeds 3800 chars (safety margin before 4096 limit), truncate timeline and append "... and N more events"
   - Return empty string if no records (graceful behavior for non-sync workflows)
5. Add module docstring explaining contract and edge cases (malformed diffs logged but don't crash, missing fields use safe defaults)
6. Create test file `tests/unit/test_telegram_sync_formatters.py` with comprehensive test coverage
7. Write tests:
   - Happy path: normal sync record, drift event with field diffs, rendered correctly
   - Edge cases: missing planned_item_key, missing title, empty field_diffs, malformed event structure
   - Truncation: long titles (50+ chars), long timeline (20 records, must truncate), message size validation
   - Status symbols: verify correct symbol for each status (SUCCEEDED, DRIFT_DETECTED, FAILED)
8. Verify formatters follow existing code patterns from `workflows.py` for consistency (defensive `.get()`, safe string concatenation, list comprehensions for iteration)
9. Run linting and type checking to confirm code quality

## Must-Haves

- [ ] `format_sync_record()` produces concise, single-line summary with status symbol
- [ ] `format_drift_event()` extracts field_diffs and renders human-readable before/after changes
- [ ] `format_sync_timeline()` respects Telegram message size limits (graceful truncation)
- [ ] All edge cases handled without exceptions (missing fields, malformed data)
- [ ] Formatters follow existing code patterns from `workflows.py` for consistency
- [ ] All unit tests green (8+ tests covering happy path and edge cases)

## Verification

- `pytest tests/unit/test_telegram_sync_formatters.py -v` — All formatter tests pass
- `ruff check apps/telegram-bot/src/helm_telegram_bot/formatters/sync_events.py` — No linting issues
- `black --check apps/telegram-bot/src/helm_telegram_bot/formatters/sync_events.py` — Code formatting correct
- Manual verification: Call formatters with sample sync records and drift events; verify output is readable and under 4096 chars

## Observability Impact

- Signals added: DEBUG-level structured log when formatters execute (record count, truncation flag if timeline was cut)
- How a future agent inspects: Grep logs for "sync_timeline_formatted" to see formatting events; check truncation_applied flag if messages were cut
- Failure state exposed: Formatter exceptions (e.g., malformed field_diffs) are caught, logged with context, and substituted with a fallback message (e.g., "Event drifted; see logs for details")

## Inputs

- T01 output: `list_sync_events()` provides the structure of sync records and events
- Existing `workflows.py` formatters — pattern for defensive dict access, string concatenation, and list handling
- S02 summary — confirms field_diffs format (dict of before/after values) and drift event structure

## Expected Output

- New file `apps/telegram-bot/src/helm_telegram_bot/formatters/sync_events.py` with three formatter functions
- New file `tests/unit/test_telegram_sync_formatters.py` with 8+ passing tests
- Formatters produce readable, Telegram-safe messages (< 4096 chars, no unescaped special chars)
- Code passes linting, type checking, and formatting checks
