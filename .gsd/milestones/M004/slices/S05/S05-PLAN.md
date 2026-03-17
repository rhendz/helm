# S05: Strict test boundaries and real E2E calendar coverage

**Goal:** E2E tests write to a staging calendar (not "primary"), read back events, assert correct local times in OPERATOR_TIMEZONE, and clean up deterministically; unit/integration/E2E layers are strictly separated with no mocks leaking across boundaries.
**Demo:** `HELM_E2E=true HELM_CALENDAR_TEST_ID=<staging> pytest tests/e2e/ -v` creates real Calendar events at correct local times, asserts timezone correctness, and cleans up. `pytest tests/e2e/` without `HELM_E2E` skips cleanly. `pytest tests/unit/test_google_calendar_adapter.py` passes (formerly misclassified integration test).

## Must-Haves

- `tests/integration/test_google_calendar_adapter_real_api.py` moved to `tests/unit/test_google_calendar_adapter.py` — the file has 98 Mock calls and zero real API calls, it is a unit test (R113)
- `tests/e2e/conftest.py` enforces `HELM_E2E=true` required for any E2E test to run; tests skip (not fail) when `HELM_E2E` is absent
- `tests/e2e/conftest.py` enforces `HELM_CALENDAR_TEST_ID` present and not "primary" — fails fast with clear error if violated (R114)
- `GoogleCalendarAdapter.upsert_calendar_block` and `reconcile_calendar_block` read `calendar_id` from `payload["calendar_id"]` instead of hardcoding `"primary"` (R114)
- `_run_calendar_agent` in `workflow_runs.py` reads `os.getenv("HELM_CALENDAR_TEST_ID", "primary")` to set `CalendarAgentOutput.calendar_id` — single-point override for E2E (R114)
- `execute_task_run` in `workflow_status_service.py` reads `os.getenv("HELM_CALENDAR_TEST_ID", "primary")` for `CalendarAgentOutput.calendar_id` (R114)
- Both E2E test files use `HELM_CALENDAR_TEST_ID` in cleanup fixtures (not hardcoded "primary")
- E2E full-stack test asserts event start times in OPERATOR_TIMEZONE match the local times from the request text (R103, R114)
- New `tests/integration/test_task_execution_integration.py` exercises `/task` → DB state path with real Postgres, mocked LLM and Calendar (R113)

## Proof Level

- This slice proves: integration + final-assembly (real Calendar API assertions for timezone correctness)
- Real runtime required: yes (staging Google Calendar for E2E; test Postgres for integration)
- Human/UAT required: no

## Verification

- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_google_calendar_adapter.py -v` — all tests pass (moved file)
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/integration/test_task_execution_integration.py -v` — passes with test Postgres
- `HELM_E2E=true HELM_CALENDAR_TEST_ID=primary OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/e2e/ -v` — errors immediately with "HELM_CALENDAR_TEST_ID must not be 'primary'"
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/e2e/ -v` — skipped (HELM_E2E not set)
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py -v` — full suite passes, no regressions
- When run with real staging calendar: `HELM_E2E=true HELM_CALENDAR_TEST_ID=<staging_id> OPERATOR_TIMEZONE=America/Los_Angeles ... pytest tests/e2e/ -v -s` — events created at correct local times, timezone assertions pass

## Observability / Diagnostics

- Runtime signals: structlog entries from `upsert_calendar_block` and `reconcile_calendar_block` now include the resolved `calendar_id` (not always "primary")
- Inspection surfaces: `HELM_CALENDAR_TEST_ID` env var presence; E2E conftest fail-fast error message
- Failure visibility: E2E conftest raises `pytest.fail()` with descriptive message if `HELM_CALENDAR_TEST_ID` is missing or "primary" when `HELM_E2E=true`
- Redaction constraints: none (calendar IDs are not secrets)

## Integration Closure

- Upstream surfaces consumed: S02's `compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard` (timezone primitives); S03's `execute_task_run`, `execute_after_approval` (inline execution); S02's `OPERATOR_TIMEZONE` config
- New wiring introduced in this slice: `calendar_id` threaded from `CalendarAgentOutput.calendar_id` through payload to `GoogleCalendarAdapter` API calls; `HELM_CALENDAR_TEST_ID` env var override in `_run_calendar_agent` and `execute_task_run`
- What remains before the milestone is truly usable end-to-end: S06 (dev experience, observability, cleanup)

## Tasks

- [x] **T01: Move misclassified calendar adapter test to unit layer** `est:15m`
  - Why: `tests/integration/test_google_calendar_adapter_real_api.py` has 98 Mock calls and zero real API calls — it's a unit test living in the wrong directory, violating R113's test layer separation policy
  - Files: `tests/integration/test_google_calendar_adapter_real_api.py` → `tests/unit/test_google_calendar_adapter.py`
  - Do: `git mv` the file; verify all tests pass from the new location; confirm no other file imports from the old path
  - Verify: `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_google_calendar_adapter.py -v` passes; old path no longer exists
  - Done when: file lives in `tests/unit/`, all tests pass, no references to old path remain

- [x] **T02: Add E2E safety guards and thread calendar_id through adapter** `est:1h`
  - Why: E2E tests currently hardcode `calendarId="primary"` everywhere and have no guard preventing accidental writes to the operator's real calendar. This is the core plumbing that makes safe E2E testing possible (R114, R113)
  - Files: `tests/e2e/conftest.py`, `packages/connectors/src/helm_connectors/google_calendar.py`, `apps/worker/src/helm_worker/jobs/workflow_runs.py`, `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`, `tests/e2e/test_weekly_scheduling_calendar_e2e.py`, `tests/e2e/test_weekly_scheduling_full_stack_e2e.py`
  - Do: (1) Add `HELM_E2E` + `HELM_CALENDAR_TEST_ID` guards to `tests/e2e/conftest.py`; (2) make `upsert_calendar_block` and `reconcile_calendar_block` read `calendar_id` from payload; (3) make `_run_calendar_agent` and `execute_task_run` read `HELM_CALENDAR_TEST_ID` env var; (4) update both E2E test files to use staging calendar ID in cleanup and all API calls
  - Verify: `HELM_E2E=true HELM_CALENDAR_TEST_ID=primary ... pytest tests/e2e/ -v` errors; `pytest tests/e2e/ -v` (no HELM_E2E) skips; full unit+integration suite still passes
  - Done when: no `calendarId="primary"` hardcoded in E2E test files; adapter reads `calendar_id` from payload; safety guards prevent primary calendar writes in E2E

- [x] **T03: Add timezone correctness assertions to E2E full-stack test** `est:45m`
  - Why: The ultimate proof for R103 — after a full-stack E2E run creates Calendar events, fetch each one and assert the start time in OPERATOR_TIMEZONE matches the local hour from the request text. This is the assertion that would have caught the original timezone bug.
  - Files: `tests/e2e/test_weekly_scheduling_full_stack_e2e.py`
  - Do: Add a new test step (test_07) that fetches each created event from the staging calendar, parses `start.dateTime`, converts to OPERATOR_TIMEZONE, and asserts the hour matches the expected local time from `_WEEKLY_REQUEST` ("10am", "2pm", "9am")
  - Verify: With real staging calendar: the new assertion passes. Without staging calendar: the test skips cleanly with the existing credential/HELM_E2E gate
  - Done when: timezone correctness assertion exists in the E2E suite; passes against staging calendar

- [x] **T04: Add /task → DB state integration test** `est:45m`
  - Why: S03's known limitation — no integration test for the full `/task` → execute_task_run → DB state chain. This test exercises the path with real Postgres but mocked LLM and Calendar, filling the gap (R113)
  - Files: `tests/integration/test_task_execution_integration.py` (new)
  - Do: Create integration test that: (1) creates a `task_quick_add` workflow run via `TelegramWorkflowStatusService.start_task_run`; (2) calls `execute_task_run` with mocked LLM + Calendar; (3) asserts `status=blocked, needs_action=True`; (4) calls `execute_after_approval` with mocked Calendar; (5) asserts `status=completed, needs_action=False`. Uses time-freeze pattern (2099-01-07) to avoid `past_event_guard` flakiness.
  - Verify: `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/integration/test_task_execution_integration.py -v` passes
  - Done when: integration test passes with real Postgres, mocked external APIs; DB state transitions verified

## Files Likely Touched

- `tests/integration/test_google_calendar_adapter_real_api.py` → `tests/unit/test_google_calendar_adapter.py` (move)
- `tests/e2e/conftest.py` (safety guards)
- `packages/connectors/src/helm_connectors/google_calendar.py` (calendar_id from payload)
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` (HELM_CALENDAR_TEST_ID env var)
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` (HELM_CALENDAR_TEST_ID env var)
- `tests/e2e/test_weekly_scheduling_calendar_e2e.py` (staging calendar ID plumbing + cleanup)
- `tests/e2e/test_weekly_scheduling_full_stack_e2e.py` (staging calendar ID + timezone assertions)
- `tests/integration/test_task_execution_integration.py` (new file)
