---
estimated_steps: 8
estimated_files: 2
---

# T01: Sync Event Query Interface

**Slice:** S03 — Telegram Real-Time Execution UX
**Milestone:** M003

## Description

Extend `TelegramWorkflowStatusService` to expose sync records and events scoped to a workflow run. The service will query both `WorkflowSyncRecordRepository` (for sync state) and `WorkflowEventRepository` (for drift events), then return structured data ready for formatting.

This task establishes the data layer; T02 and T03 will format and display the data.

## Steps

1. Read existing `WorkflowStatusService._build_completion_summary()` to understand how sync counts are computed and ensure no duplication
2. Review `WorkflowSyncRecordRepository.list_for_run()` and `WorkflowEventRepository.list_for_run_by_type()` interfaces to confirm available query methods
3. Add `list_sync_events(run_id: int) -> list[dict[str, object]]` method to `TelegramWorkflowStatusService` that:
   - Queries sync records via `WorkflowSyncRecordRepository(session).list_for_run(run_id)`
   - Queries drift events via `WorkflowEventRepository(session).list_for_run_by_type(run_id, event_type='drift_detected_external_change')`
   - Returns a list of dicts, each containing: sync_record_id, planned_item_key, status, external_object_id, created_at, last_error_summary (for drift metadata), and a reference to associated drift_event if present
   - Sort by created_at descending (most recent first)
4. Add `get_sync_details(run_id: int) -> dict[str, object]` method that:
   - Calls `list_sync_events()` and computes total/task/calendar counts from the records
   - Reuses logic from `_build_completion_summary()` to avoid duplication
   - Returns dict with keys: sync_records, drift_events, total_sync_writes, task_sync_writes, calendar_sync_writes
5. Add comprehensive docstrings explaining the return structure and edge cases (empty results, missing events)
6. Create unit test file `tests/unit/test_telegram_sync_queries.py` with tests for both methods
7. Write tests covering happy path (normal runs with multiple sync records), empty results (no syncs), drift events present, and data type validation
8. Run full test suite to confirm zero regressions

## Must-Haves

- [ ] `list_sync_events()` method returns properly-typed list of dicts with all expected fields
- [ ] `get_sync_details()` method aggregates counts correctly without duplicating WorkflowStatusService logic
- [ ] Queries use existing repository methods (no new SQL or raw queries)
- [ ] Edge cases handled defensively (missing events, incomplete metadata, empty results)
- [ ] All tests green; zero regressions in existing tests

## Verification

- `pytest tests/unit/test_telegram_sync_queries.py -v` — All unit tests pass
- `pytest tests/ -v` — Full test suite passes with no regressions
- Manual inspection: Call methods in a test context and verify return structure matches expected schema (list of dicts with sync_record_id, status, etc.)

## Observability Impact

- Signals added: Structured log at DEBUG level when sync queries execute (count of records, events, durations)
- How a future agent inspects: Query database `SELECT * FROM workflow_sync_records WHERE workflow_run_id=X ORDER BY created_at DESC` to see raw state; grep logs for "sync_events_queried" to see query counts
- Failure state exposed: If sync records are missing or events have incomplete metadata, logs include the record count and which fields are missing

## Inputs

- `WorkflowStatusService._build_completion_summary()` — pattern for aggregating sync counts
- `WorkflowSyncRecordRepository.list_for_run()` — existing method to fetch sync records
- `WorkflowEventRepository.list_for_run_by_type()` — existing method to fetch events by type
- S02 summary — confirms sync records are populated with status, external_object_id, and drift metadata

## Expected Output

- `TelegramWorkflowStatusService.list_sync_events()` method producing list of properly-typed dicts
- `TelegramWorkflowStatusService.get_sync_details()` method returning aggregated sync data
- `tests/unit/test_telegram_sync_queries.py` with 5+ passing tests
- Zero regressions in existing test suite
