---
estimated_steps: 7
estimated_files: 3
---

# T01: Add timezone primitives to scheduling.py and unit-test them

**Slice:** S02 — Timezone correctness and shared scheduling primitives
**Milestone:** M004

## Description

Add four pure timezone-aware scheduling functions to `packages/orchestration/src/helm_orchestration/scheduling.py`, export them from `__init__.py`, and write comprehensive unit tests in `tests/unit/test_scheduling_primitives.py`.

These functions are the foundation that `workflow_runs.py` (T03) and future scheduling paths depend on. They have no DB, network, or config dependencies — pure functions over `datetime` and `ZoneInfo`. Test them thoroughly here so the worker refactor (T03) only needs to trust the contracts.

**Functions to implement:**

```python
def compute_reference_week(tz: ZoneInfo) -> datetime:
    """Return the Monday of the current week at midnight in the given timezone.
    
    'Current week' means the ISO week containing today in the given timezone.
    If today is Sunday, returns the Monday 6 days ago (ISO week convention —
    week starts on Monday). The returned datetime is timezone-aware (tzinfo=tz).
    """

def parse_local_slot(title: str, week_start: datetime, tz: ZoneInfo) -> datetime | None:
    """Extract day + start time from a task title like 'Monday deep work 10am-12pm'.
    
    Returns a timezone-aware datetime in `tz` for the named day at the named time,
    relative to the Monday of `week_start`'s week. Returns None if no day or time
    can be parsed.
    
    Behavior:
    - Searches title for day name (monday, tuesday, ..., sunday)
    - Searches for a time range (e.g. '10am-12pm') first, then a single time (e.g. '10am')
    - If day found but no time, defaults to 9am local
    - If no day found, returns None
    - Returned datetime is always timezone-aware (tzinfo=tz), NOT UTC
    """

def to_utc(local_dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert a local datetime to UTC.
    
    If `local_dt` is already timezone-aware, returns it converted to UTC.
    If `local_dt` is naive, treats it as being in `tz`, then converts to UTC.
    """

def past_event_guard(dt: datetime, tz: ZoneInfo) -> None:
    """Raise PastEventError if dt is in the past relative to now in tz.
    
    Compares `dt` (converted to UTC) against `datetime.now(UTC)`.
    Raises PastEventError with a descriptive message if the datetime is in the past.
    """
```

Also define `PastEventError(ValueError)` in `scheduling.py` — a named exception class so callers can catch it specifically.

**Important constraints:**
- `zoneinfo.ZoneInfo` is Python 3.11+ stdlib — no external timezone library needed
- `ConditionalApprovalPolicy.evaluate(semantics: TaskSemantics)` must NOT be changed — S01 wired this and 22 unit tests depend on it
- The day/time parsing logic in `parse_local_slot` should preserve the same regex-based approach already in `_parse_slot_from_title` in `workflow_runs.py` (lines 340–409) — extract it, make it return a tz-aware datetime instead of a UTC datetime

## Steps

1. **Add `PastEventError` class** to `scheduling.py` just before the existing `ApprovalPolicy` Protocol:
   ```python
   class PastEventError(ValueError):
       """Raised when a scheduled datetime is in the past."""
   ```

2. **Add the four primitive functions** after `ConditionalApprovalPolicy`. Copy the `_DAY_OFFSETS`, `_TIME_PATTERN`, and `_RANGE_PATTERN` regex constants from `workflow_runs.py` into `scheduling.py` (they belong here now). Implement each function exactly per the docstrings above.
   
   Key implementation notes:
   - `compute_reference_week`: `now = datetime.now(tz)` → `now - timedelta(days=now.weekday())` → replace hour/min/sec/µsec with 0 → return tz-aware Monday midnight
   - `parse_local_slot`: mirror the existing `_parse_slot_from_title` logic but use `tz` to build `base_day` (i.e., `base_day = (week_monday + timedelta(days=day_offset)).replace(tzinfo=tz)`). The `week_monday` calculation: `week_start - timedelta(days=week_start.weekday())` — same logic as before. Return value is tz-aware (not UTC).
   - `to_utc`: if `local_dt.tzinfo` is not None → `local_dt.astimezone(UTC)`; else → `local_dt.replace(tzinfo=tz).astimezone(UTC)`
   - `past_event_guard`: `utc_dt = to_utc(dt, tz)` → if `utc_dt < datetime.now(UTC)` → raise `PastEventError(f"Scheduled datetime {utc_dt.isoformat()} is in the past")`

3. **Update `__init__.py`** imports section — add to the `from helm_orchestration.scheduling import ...` line:
   ```python
   from helm_orchestration.scheduling import (
       ApprovalPolicy,
       ConditionalApprovalPolicy,
       PastEventError,
       compute_reference_week,
       parse_local_slot,
       past_event_guard,
       to_utc,
   )
   ```
   Add all five new names to `__all__`.

4. **Write `tests/unit/test_scheduling_primitives.py`** with at minimum these test cases:
   - `test_compute_reference_week_returns_monday`: result has `weekday() == 0`
   - `test_compute_reference_week_is_tz_aware`: result `tzinfo` is not None
   - `test_compute_reference_week_midnight`: result hour/minute/second all 0
   - `test_parse_local_slot_day_and_time`: `parse_local_slot("Monday deep work 10am", week_start, tz)` → `hour == 10`, `tzinfo is not None`
   - `test_parse_local_slot_range`: `parse_local_slot("Tuesday 10am-12pm", ...)` → `hour == 10`
   - `test_parse_local_slot_no_day_returns_none`: `parse_local_slot("deep work 10am", ...)` → `None`
   - `test_parse_local_slot_day_no_time_defaults_9am`: `parse_local_slot("Wednesday deep work", ...)` → `hour == 9`
   - `test_to_utc_naive_input`: naive datetime in PDT converts to `hour+7` in UTC (or +8 in winter)
   - `test_to_utc_aware_input`: already-aware datetime converts correctly
   - `test_past_event_guard_future_does_not_raise`: far-future datetime → no exception
   - `test_past_event_guard_past_raises`: 2020 datetime → raises `PastEventError`
   - `test_past_event_guard_past_raises_type`: confirm `isinstance(exc, ValueError)`
   
   Use `ZoneInfo("America/Los_Angeles")` as the test timezone throughout. For `test_to_utc_naive_input`, use a fixed datetime (e.g. `datetime(2026, 6, 15, 10, 0)` — summer, PDT = UTC-7) to make the expected UTC offset deterministic.

5. **Run verification**:
   ```bash
   cd /path/to/repo && .venv/bin/python -m pytest tests/unit/test_scheduling_primitives.py -v
   .venv/bin/python -m pytest tests/unit/test_task_inference.py -v
   ```

## Must-Haves

- [ ] `PastEventError` defined as a named exception in `scheduling.py`
- [ ] All four functions implemented in `scheduling.py` with correct tz-aware return values
- [ ] `parse_local_slot` returns tz-aware datetimes in the given `tz` (NOT UTC)
- [ ] All five new names (`PastEventError`, `compute_reference_week`, `parse_local_slot`, `past_event_guard`, `to_utc`) exported from `helm_orchestration.__init__.py` and in `__all__`
- [ ] `tests/unit/test_scheduling_primitives.py` exists with ≥12 test cases, all passing
- [ ] `pytest tests/unit/test_task_inference.py` still passes (no regression to `ConditionalApprovalPolicy`)

## Verification

- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && .venv/bin/python -m pytest tests/unit/test_scheduling_primitives.py -v` → all pass
- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && .venv/bin/python -m pytest tests/unit/test_task_inference.py -v` → all pass (no regression)
- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && .venv/bin/python -c "from helm_orchestration import compute_reference_week, parse_local_slot, to_utc, past_event_guard, PastEventError; print('ok')"` → prints "ok"

## Inputs

- `packages/orchestration/src/helm_orchestration/scheduling.py` — existing file with `ApprovalPolicy` Protocol and `ConditionalApprovalPolicy`; add below these
- `packages/orchestration/src/helm_orchestration/__init__.py` — existing file; add new imports and `__all__` entries
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` lines 329–409 — reference implementation of `_candidate_slots` and `_parse_slot_from_title`; copy regex constants, adapt parsing logic to return tz-aware datetime

## Expected Output

- `packages/orchestration/src/helm_orchestration/scheduling.py` — expanded with `PastEventError`, `_DAY_OFFSETS`, `_TIME_PATTERN`, `_RANGE_PATTERN`, and four new pure functions
- `packages/orchestration/src/helm_orchestration/__init__.py` — imports and `__all__` updated with five new exports
- `tests/unit/test_scheduling_primitives.py` — new file with ≥12 passing tests covering all four primitives and failure paths
