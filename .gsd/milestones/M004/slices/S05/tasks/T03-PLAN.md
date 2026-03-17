---
estimated_steps: 4
estimated_files: 1
---

# T03: Add timezone correctness assertions to E2E full-stack test

**Slice:** S05 — Strict test boundaries and real E2E calendar coverage
**Milestone:** M004

## Description

The ultimate proof for R103: after the full-stack E2E test creates Calendar events via `apply_schedule`, fetch each event from the staging calendar, parse its `start.dateTime`, convert to OPERATOR_TIMEZONE, and assert the hour/minute match the local time specified in the request text.

The `_WEEKLY_REQUEST` in the full-stack test specifies:
- "Monday E2E test deep work **10am**-12pm"
- "Tuesday E2E test team sync **2pm**-3pm"  
- "Wednesday E2E test focus block **9am**-11am"

After T02 threads `calendar_id` through the adapter, all events land on the staging calendar. This task adds a new test step that reads them back and verifies the start hours are 10, 14, and 9 respectively in `OPERATOR_TIMEZONE`.

**Depends on T02** — the E2E safety guards and `calendar_id` threading must be in place first.

## Steps

1. **Add `test_07_events_have_correct_local_times` to `TestWeeklySchedulingFullStackE2E`** in `tests/e2e/test_weekly_scheduling_full_stack_e2e.py`:

   ```python
   def test_07_events_have_correct_local_times(self) -> None:
       """Fetch each event and assert start time matches OPERATOR_TIMEZONE local hour (R103)."""
       from datetime import datetime as dt_cls
       from zoneinfo import ZoneInfo

       assert self.created_event_ids, "No event IDs — step 4 must have failed"

       tz = ZoneInfo(os.environ["OPERATOR_TIMEZONE"])
       calendar_id = os.environ["HELM_CALENDAR_TEST_ID"]

       adapter = GoogleCalendarAdapter(GoogleCalendarAuth())
       service = adapter._get_service()

       # Expected local start hours from _WEEKLY_REQUEST
       # Order matches the order events are created (Mon, Tue, Wed)
       expected_hours = [10, 14, 9]

       for event_id, expected_hour in zip(self.created_event_ids, expected_hours):
           event = service.events().get(
               calendarId=calendar_id, eventId=event_id
           ).execute()
           start_str = event["start"]["dateTime"]
           start_local = dt_cls.fromisoformat(start_str).astimezone(tz)
           assert start_local.hour == expected_hour, (
               f"Expected hour {expected_hour} in {tz}, got {start_local.hour} "
               f"(raw: {start_str}) for event '{event.get('summary')}'"
           )
   ```

2. **Verify the expected hour mapping is correct** by cross-referencing with `_WEEKLY_REQUEST`:
   - "Monday E2E test deep work 10am-12pm" → `parse_local_slot` extracts 10am → expected_hour=10
   - "Tuesday E2E test team sync 2pm-3pm" → `parse_local_slot` extracts 2pm → expected_hour=14
   - "Wednesday E2E test focus block 9am-11am" → `parse_local_slot` extracts 9am → expected_hour=9

3. **Add the `os` import** at the top of the file if not already present (it likely is from T02's changes).

4. **Run the full test suite** to confirm no regressions:
   ```bash
   OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ \
     --ignore=tests/unit/test_study_agent_mvp.py -q
   ```
   The new test step won't execute without `HELM_E2E=true` + staging credentials, but the file must still parse and collect cleanly.

## Must-Haves

- [ ] `test_07_events_have_correct_local_times` exists in `TestWeeklySchedulingFullStackE2E`
- [ ] Assertion converts `event["start"]["dateTime"]` to OPERATOR_TIMEZONE and checks the hour
- [ ] Expected hours (10, 14, 9) match `_WEEKLY_REQUEST` titles
- [ ] Test uses staging calendar ID from `HELM_CALENDAR_TEST_ID` (not "primary")

## Verification

- File parses and collects without error:
  ```bash
  OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/e2e/test_weekly_scheduling_full_stack_e2e.py --collect-only 2>&1 | grep "test_07"
  ```
  → Shows `test_07_events_have_correct_local_times` in the collection output

- Full unit+integration suite still passes:
  ```bash
  OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ \
    --ignore=tests/unit/test_study_agent_mvp.py -q
  ```

- When run with real staging calendar (manual verification):
  ```bash
  HELM_E2E=true HELM_CALENDAR_TEST_ID=<staging_id> OPERATOR_TIMEZONE=America/Los_Angeles \
    GOOGLE_CLIENT_ID=xxx GOOGLE_CLIENT_SECRET=xxx GOOGLE_REFRESH_TOKEN=xxx \
    uv run --frozen --extra dev pytest tests/e2e/test_weekly_scheduling_full_stack_e2e.py -v -s
  ```
  → `test_07_events_have_correct_local_times` passes with correct hour assertions

## Inputs

- `tests/e2e/test_weekly_scheduling_full_stack_e2e.py` — after T02's changes, uses staging calendar ID throughout
- `_WEEKLY_REQUEST` constant in the test file — specifies "Monday 10am-12pm", "Tuesday 2pm-3pm", "Wednesday 9am-11am"
- `self.created_event_ids` — populated by `test_04_worker_applies_schedule`
- S02's `parse_local_slot` correctly extracts hours from titles like "Monday deep work 10am-12pm" (proven by 18 unit tests)

## Expected Output

- `tests/e2e/test_weekly_scheduling_full_stack_e2e.py` — has `test_07_events_have_correct_local_times` that fetches events from staging calendar and asserts start hour in OPERATOR_TIMEZONE matches expected local hour

## Observability Impact

**What changes:** A new test step (`test_07_events_have_correct_local_times`) fetches live Calendar events and asserts `start.dateTime` converts to the expected local hour in `OPERATOR_TIMEZONE`. No new runtime log signals are emitted — the observability lives in the test assertion failure message.

**How a future agent inspects this task:**
- `pytest tests/e2e/test_weekly_scheduling_full_stack_e2e.py --collect-only 2>&1 | grep test_07` — confirms the step is collected
- On assertion failure, the message surfaces: `Expected hour {N} in {tz}, got {actual} (raw: {iso_string}) for event '{summary}'` — this pinpoints whether the bug is in IANA timezone resolution, UTC offset math, or the wrong event being checked.
- `OPERATOR_TIMEZONE` env var must be set; if absent, `os.environ["OPERATOR_TIMEZONE"]` raises `KeyError` immediately, making the misconfiguration visible.

**Failure state visibility:**
- If an event was stored in UTC without tz conversion, the raw `start_str` will have a UTC offset (`+00:00`) and `start_local.hour` will differ from the expected local hour by the UTC offset amount — the error message exposes both the raw ISO string and the converted hour.
- If `HELM_CALENDAR_TEST_ID` points to the wrong calendar, the `service.events().get()` call will raise a 404, making the misconfiguration immediately visible.
