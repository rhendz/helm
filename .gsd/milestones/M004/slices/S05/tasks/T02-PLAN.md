---
estimated_steps: 8
estimated_files: 6
---

# T02: Add E2E safety guards and thread calendar_id through adapter

**Slice:** S05 — Strict test boundaries and real E2E calendar coverage
**Milestone:** M004

## Description

E2E tests currently hardcode `calendarId="primary"` everywhere and have no guard preventing writes to the operator's real calendar. This task adds three safety layers:

1. **E2E conftest guards**: `HELM_E2E=true` required for E2E tests to run (skip if absent); `HELM_CALENDAR_TEST_ID` must be present and not "primary" when `HELM_E2E=true` (fail-fast if violated).
2. **`calendar_id` threading in adapter**: `GoogleCalendarAdapter.upsert_calendar_block` and `reconcile_calendar_block` read `calendar_id` from the request payload instead of hardcoding "primary".
3. **`HELM_CALENDAR_TEST_ID` env var override**: `_run_calendar_agent` (weekly workflow) and `execute_task_run` (task path) read `os.getenv("HELM_CALENDAR_TEST_ID", "primary")` so E2E tests route to the staging calendar without code patches.
4. **E2E test files updated**: cleanup fixtures and direct API calls use the staging calendar ID, not "primary".

Per D007: E2E tests skip (not fail) if env vars absent, but fail explicitly if `HELM_CALENDAR_TEST_ID=primary`.

## Observability Impact

**Signals added by this task:**
- `upsert_calendar_block: calling events.update` and `upsert_calendar_block: calling events.insert` structlog entries now include `calendar_id` field — directly observable which calendar is being written.
- `upsert_calendar_block_success` structlog entry now includes `calendar_id` — confirms the actual calendar that received the event.
- `reconcile_calendar_block: calling events.get` structlog entry now includes `calendar_id` — confirms which calendar is being reconciled against.

**Inspection surfaces:**
- `HELM_CALENDAR_TEST_ID` env var: if set, all calendar writes/reads route to that calendar ID instead of "primary". Absence means "primary" is used.
- `HELM_E2E` env var: if absent, all E2E tests skip. If present without `HELM_CALENDAR_TEST_ID`, tests fail immediately with a descriptive error.
- `pytest_configure` in `tests/e2e/conftest.py` will `pytest.exit()` with "must not be 'primary'" if a misconfigured run is attempted.

**Failure visibility:**
- If E2E tests run against the wrong calendar, structlog entries at `upsert_calendar_block_success` will show the `calendar_id` that was used — enabling post-hoc diagnosis.
- If `HELM_CALENDAR_TEST_ID=primary` is set with `HELM_E2E=true`, pytest exits before any test runs with a clear error message. No events will be created.
- `_reconcile_sync_record` now propagates `calendar_id` from the sync record's payload, so reconciliation drift detection also operates on the correct calendar.

## Steps

1. **Update `tests/e2e/conftest.py`** — add safety guards:
   ```python
   import os
   import pytest

   # ... existing DATABASE_URL override ...

   # ---------------------------------------------------------------------------
   # E2E safety gates (D007)
   # ---------------------------------------------------------------------------
   _HELM_E2E = os.getenv("HELM_E2E", "").lower() == "true"
   _CALENDAR_TEST_ID = os.getenv("HELM_CALENDAR_TEST_ID", "")

   def pytest_collection_modifyitems(config, items):
       """Skip all E2E tests when HELM_E2E is not set."""
       if _HELM_E2E:
           return
       skip_marker = pytest.mark.skip(reason="HELM_E2E not set — skipping E2E tests")
       for item in items:
           item.add_marker(skip_marker)

   def pytest_configure(config):
       """Fail fast if HELM_E2E is set but HELM_CALENDAR_TEST_ID is missing or 'primary'."""
       if not _HELM_E2E:
           return
       if not _CALENDAR_TEST_ID:
           pytest.exit("HELM_CALENDAR_TEST_ID must be set when HELM_E2E=true", returncode=1)
       if _CALENDAR_TEST_ID.lower() == "primary":
           pytest.exit("HELM_CALENDAR_TEST_ID must not be 'primary' — use a staging calendar ID", returncode=1)

   @pytest.fixture(scope="session")
   def e2e_calendar_id() -> str:
       """Return the staging calendar ID for E2E tests."""
       return _CALENDAR_TEST_ID
   ```

2. **Update `GoogleCalendarAdapter.upsert_calendar_block`** in `packages/connectors/src/helm_connectors/google_calendar.py`:
   - After extracting `payload = request.item.payload` (already exists), add:
     ```python
     calendar_id = payload.get("calendar_id") or "primary"
     ```
   - Replace all three `calendarId="primary"` occurrences in this method (lines ~248, ~260) with `calendarId=calendar_id`.
   - Add `calendar_id=calendar_id` to the structlog entries for traceability.

3. **Update `GoogleCalendarAdapter.reconcile_calendar_block`** in the same file:
   - The method receives a `SyncLookupRequest` object, not a payload dict. Add a `calendar_id: str = "primary"` field to the `SyncLookupRequest` schema in `packages/orchestration/src/helm_orchestration/schemas.py`.
   - In `reconcile_calendar_block`, read `request.calendar_id` and use it instead of the hardcoded `"primary"` on the `events().get(calendarId=...)` call (line ~472).

4. **Update `SyncLookupRequest` schema** in `packages/orchestration/src/helm_orchestration/schemas.py`:
   ```python
   class SyncLookupRequest(BaseModel):
       model_config = ConfigDict(extra="forbid")
       proposal_artifact_id: int
       proposal_version_number: int
       target_system: SyncTargetSystem
       operation: SyncOperation
       planned_item_key: str
       payload_fingerprint: str
       external_object_id: str | None = None
       calendar_id: str = "primary"  # NEW — staging calendar override for E2E
   ```

5. **Update `_reconcile_sync_record` in `workflow_service.py`** to pass `calendar_id` from the sync record's payload:
   - In `_reconcile_sync_record` (around line 1698), the `SyncLookupRequest` is built from `sync_record` fields. The sync record's payload contains `calendar_id`. Read it:
     ```python
     # After building the SyncLookupRequest, before the if/else:
     # If this is a calendar record, propagate calendar_id from the sync record's payload
     payload = sync_record.payload if hasattr(sync_record, 'payload') else {}
     if isinstance(payload, dict):
         lookup = SyncLookupRequest(
             ...,
             calendar_id=payload.get("calendar_id") or "primary",
         )
     ```
   - **Important**: The existing `SyncLookupRequest` construction needs the `calendar_id` field added. Check if `sync_record` has a `payload` attribute accessible at this point. If not, check the sync record model. The payload was stored when the `ApprovedSyncItem` was persisted — it should be available on the record as a JSON dict.

6. **Update `_run_calendar_agent` in `apps/worker/src/helm_worker/jobs/workflow_runs.py`**:
   - Find the line `calendar_id="primary"` (around line 247 on the milestone/M004 branch).
   - Replace with: `calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary")`
   - Import `os` at the top of the file if not already imported.
   - Do the same for the second occurrence around line 442 (if there is one — the weekly scheduling path also sets `calendar_id`).

7. **Update `execute_task_run` in `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`**:
   - Find `calendar_id="primary"` (line ~95).
   - Replace with: `calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary")`
   - Import `os` at the top of the file if not already imported.

8. **Update both E2E test files to use the staging calendar ID**:

   In `tests/e2e/test_weekly_scheduling_calendar_e2e.py`:
   - Remove the existing per-test `_CREDS_PRESENT` skip marker (the conftest now handles skipping).
   - Update the `adapter` fixture to accept `e2e_calendar_id` from conftest (or just use the env var directly).
   - In the `cleanup` fixture, replace `calendarId="primary"` with the staging calendar ID (read from `os.getenv("HELM_CALENDAR_TEST_ID", "primary")`).
   - In `_make_request`, add `"calendar_id": os.getenv("HELM_CALENDAR_TEST_ID", "primary")` to the payload dict.
   - In `test_drift_detected_after_manual_edit`, the out-of-band `events().patch(calendarId="primary", ...)` call must also use the staging ID.
   - In `test_deleted_event_returns_not_found`, the out-of-band `events().delete(calendarId="primary", ...)` call must use the staging ID.
   - In all `SyncLookupRequest(...)` constructions, add `calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary")`.

   In `tests/e2e/test_weekly_scheduling_full_stack_e2e.py`:
   - Remove the existing `_CREDS_PRESENT` skip marker.
   - In the `cleanup_calendar_events` fixture, replace `calendarId="primary"` with the staging calendar ID.
   - In `test_05_events_exist_in_google_calendar`, replace `calendarId="primary"` with the staging calendar ID.
   - In `test_06_reconcile_no_drift`, add `calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary")` to `SyncLookupRequest`.

   **Critical**: Keep credential-checking in both files as a secondary gate — the `_CREDS_PRESENT` check should remain as a module-level skip marker for when `HELM_E2E` is set but credentials are missing. Or let the conftest handle all gating. Choose one approach, be consistent.

## Must-Haves

- [ ] `tests/e2e/conftest.py` has `HELM_E2E` skip gate and `HELM_CALENDAR_TEST_ID` fail-fast guard
- [ ] `GoogleCalendarAdapter.upsert_calendar_block` reads `calendar_id` from `payload["calendar_id"]`, defaults to `"primary"`
- [ ] `GoogleCalendarAdapter.reconcile_calendar_block` reads `calendar_id` from `SyncLookupRequest.calendar_id`, defaults to `"primary"`
- [ ] `SyncLookupRequest` schema has `calendar_id: str = "primary"` field
- [ ] `_run_calendar_agent` reads `HELM_CALENDAR_TEST_ID` env var with `"primary"` fallback
- [ ] `execute_task_run` reads `HELM_CALENDAR_TEST_ID` env var with `"primary"` fallback
- [ ] Both E2E test files use staging calendar ID in cleanup fixtures and all API calls
- [ ] No remaining `calendarId="primary"` in E2E test files
- [ ] `_reconcile_sync_record` in `workflow_service.py` passes `calendar_id` to `SyncLookupRequest`
- [ ] Full unit + integration suite passes (no regressions from schema/adapter changes)

## Verification

- **Safety guard — fail on "primary":**
  ```bash
  HELM_E2E=true HELM_CALENDAR_TEST_ID=primary OPERATOR_TIMEZONE=America/Los_Angeles \
    uv run --frozen --extra dev pytest tests/e2e/ -v 2>&1 | grep -i "must not be"
  ```
  → Output contains "must not be 'primary'"

- **Safety guard — skip when HELM_E2E absent:**
  ```bash
  OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/e2e/ -v 2>&1 | grep -i "skip"
  ```
  → Tests are skipped

- **No regressions:**
  ```bash
  OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ \
    --ignore=tests/unit/test_study_agent_mvp.py -q
  ```
  → All pass

## Inputs

- `tests/e2e/conftest.py` — currently only overrides DATABASE_URL, no safety gates
- `packages/connectors/src/helm_connectors/google_calendar.py` — `upsert_calendar_block` hardcodes `calendarId="primary"` at lines ~248, ~260; `reconcile_calendar_block` hardcodes at line ~472
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `_run_calendar_agent` sets `calendar_id="primary"` at line ~247 (and possibly ~442 for weekly path)
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — `execute_task_run` sets `calendar_id="primary"` at line ~95
- `packages/orchestration/src/helm_orchestration/schemas.py` — `SyncLookupRequest` schema (no `calendar_id` field yet)
- `packages/orchestration/src/helm_orchestration/workflow_service.py` — `_reconcile_sync_record` builds `SyncLookupRequest` at line ~1698
- `tests/e2e/test_weekly_scheduling_calendar_e2e.py` — hardcodes `calendarId="primary"` in cleanup and manual patch/delete calls
- `tests/e2e/test_weekly_scheduling_full_stack_e2e.py` — hardcodes `calendarId="primary"` in cleanup and event fetch

## Expected Output

- `tests/e2e/conftest.py` — has `HELM_E2E` skip gate, `HELM_CALENDAR_TEST_ID` fail-fast, and `e2e_calendar_id` session fixture
- `packages/connectors/src/helm_connectors/google_calendar.py` — `upsert_calendar_block` and `reconcile_calendar_block` use dynamic `calendar_id`
- `packages/orchestration/src/helm_orchestration/schemas.py` — `SyncLookupRequest` has `calendar_id: str = "primary"`
- `packages/orchestration/src/helm_orchestration/workflow_service.py` — `_reconcile_sync_record` passes `calendar_id` from payload
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `_run_calendar_agent` reads `HELM_CALENDAR_TEST_ID`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — `execute_task_run` reads `HELM_CALENDAR_TEST_ID`
- `tests/e2e/test_weekly_scheduling_calendar_e2e.py` — uses staging calendar ID throughout
- `tests/e2e/test_weekly_scheduling_full_stack_e2e.py` — uses staging calendar ID throughout
