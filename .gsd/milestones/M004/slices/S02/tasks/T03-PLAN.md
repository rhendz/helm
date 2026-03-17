---
estimated_steps: 8
estimated_files: 2
---

# T03: Refactor workflow_runs.py to use shared primitives and fix RFC3339

**Slice:** S02 — Timezone correctness and shared scheduling primitives
**Milestone:** M004

## Description

Update `apps/worker/src/helm_worker/jobs/workflow_runs.py` to replace the hardcoded UTC scheduling logic with calls to the shared primitives added in T01, read `OPERATOR_TIMEZONE` from worker settings (available after T02), and fix the `replace("+00:00", "Z")` RFC3339 hack. This is the integration closure task — it directly fixes the bug that causes calendar events to land at the wrong local time.

**The core bug (line 329):**
```python
base = datetime(2026, 3, 16, 9, tzinfo=UTC)  # ← hardcoded date, UTC 9am ≠ local 9am
```

**After this task:**
- `_candidate_slots` calls `compute_reference_week(tz)` to get a dynamic, timezone-aware Monday
- `_parse_slot_from_title` is removed in favor of `parse_local_slot(title, week_start, tz)` (returns local-time datetime, not UTC)
- `_run_calendar_agent` reads `settings.operator_timezone`, constructs `ZoneInfo`, and passes it through
- `ScheduleBlock.start` and `.end` are set with `to_utc(local_dt, tz).isoformat()` — proper RFC3339 with correct offset (no `replace("+00:00", "Z")`)
- `past_event_guard(start_utc, tz)` is called before appending each `ScheduleBlock`; if it raises `PastEventError`, the slot is skipped and the task added to `carry_forward` with a warning message (NOT a hard exception — warn-and-skip pattern)

**Already-in-progress primitives (confirmed in T01):**
- `compute_reference_week(tz: ZoneInfo) -> datetime` — returns Monday midnight in local TZ
- `parse_local_slot(title: str, week_start: datetime, tz: ZoneInfo) -> datetime | None` — returns tz-aware local datetime
- `to_utc(local_dt: datetime, tz: ZoneInfo) -> datetime` — converts to UTC
- `past_event_guard(dt: datetime, tz: ZoneInfo) -> None` — raises `PastEventError` if in past
- `PastEventError` — named exception class for catching specifically

**Constraints:**
- The `_parse_duration_from_title` function can stay in `workflow_runs.py` — it's a pure string utility (no timezone involvement) and is not a scheduling primitive
- The `_priority_rank` and `_human_day` helpers also stay local
- The regex constants (`_DAY_OFFSETS`, `_TIME_PATTERN`, `_RANGE_PATTERN`) are now in `scheduling.py` (added in T01) — remove the duplicates from `workflow_runs.py`
- `_parse_slot_from_title` in `workflow_runs.py` can be deleted entirely once `_run_calendar_agent` uses `parse_local_slot`
- `_candidate_slots` can be simplified to a short function that calls `compute_reference_week`

## Steps

1. **Update imports in `workflow_runs.py`** — add imports for shared primitives and worker settings:
   ```python
   from zoneinfo import ZoneInfo
   from helm_orchestration import (
       # ... existing imports ...
       PastEventError,
       compute_reference_week,
       parse_local_slot,
       past_event_guard,
       to_utc,
   )
   from helm_worker.config import settings
   ```

2. **Remove duplicate regex constants** from `workflow_runs.py`:
   - Delete `_DAY_OFFSETS`, `_TIME_PATTERN`, `_RANGE_PATTERN` — these now live in `scheduling.py`
   - Delete `_parse_slot_from_title` function entirely — replaced by `parse_local_slot`

3. **Replace `_candidate_slots`** with a timezone-aware implementation:
   ```python
   def _candidate_slots(request: CalendarAgentInput, tz: ZoneInfo) -> list[datetime]:
       week_monday = compute_reference_week(tz)
       protected = request.weekly_request.protected_time if request.weekly_request is not None else ()
       if protected:
           return [week_monday + timedelta(days=index, hours=9) for index in range(4)]
       return [week_monday + timedelta(days=index, hours=9 + (index % 2)) for index in range(5)]
   ```
   Note: the returned datetimes are local (tz-aware in the operator timezone), not UTC. `to_utc` is called later when building `ScheduleBlock`.

4. **Update `_run_calendar_agent`** — add `tz` construction and update the scheduling loop:
   
   a. At the top of the function body, after `request = CalendarAgentInput.model_validate(payload)`:
   ```python
   tz = ZoneInfo(settings.operator_timezone)
   ```
   
   b. Update `slots = _candidate_slots(request)` → `slots = _candidate_slots(request, tz)`
   
   c. In the per-task loop, replace the explicit-start parsing:
   ```python
   # OLD:
   explicit_start = _parse_slot_from_title(task.title, reference_week_start=slot)
   start = explicit_start if explicit_start is not None else slot
   end_time = start + timedelta(minutes=duration_minutes)
   
   # NEW:
   local_start = parse_local_slot(task.title, week_start=slot, tz=tz) or slot
   start_utc = to_utc(local_start, tz)
   end_utc = start_utc + timedelta(minutes=duration_minutes)
   ```
   
   d. Add `past_event_guard` call (warn-and-skip pattern):
   ```python
   try:
       past_event_guard(start_utc, tz)
   except PastEventError as exc:
       logger.warning("past_event_guard_triggered", task_title=task.title, reason=str(exc))
       carry_forward.append(task.title)
       continue
   ```
   
   e. Fix `ScheduleBlock` construction — remove the `replace("+00:00", "Z")` hack:
   ```python
   # OLD:
   ScheduleBlock(
       title=task.title,
       task_title=task.title,
       start=start.isoformat().replace("+00:00", "Z"),
       end=end_time.isoformat().replace("+00:00", "Z"),
   )
   
   # NEW:
   ScheduleBlock(
       title=task.title,
       task_title=task.title,
       start=start_utc.isoformat(),
       end=end_utc.isoformat(),
   )
   ```

5. **Update `_human_day` helper** to show the local time (not just UTC):
   ```python
   def _human_day(value: datetime) -> str:
       local = value.astimezone() if value.tzinfo else value
       return local.strftime("%A %H:%M %Z")
   ```
   This is a minor UX improvement — the generated `proposed_changes` strings will now show local time.

6. **Run the regression suite**:
   ```bash
   cd /path/to/repo
   .venv/bin/python -m pytest tests/integration/test_weekly_scheduling_end_to_end.py -v
   .venv/bin/python -m pytest tests/integration/ -v
   .venv/bin/python -m pytest tests/unit/ -v
   ```
   
   If the integration test `test_weekly_scheduling_end_to_end.py` trips the `past_event_guard` (because the generated "this week's Monday" slots are in the past when the test runs late in the week), the warn-and-skip behavior means `carry_forward` grows but `time_blocks` may have fewer items. The test asserts `len(proposal["time_blocks"]) > 0` — this should still hold unless all 5 slots are past. If all slots end up carried forward, the test's `len(proposal["time_blocks"]) > 0` assertion will fail.
   
   **Resolution:** If this occurs, check whether the integration test needs future-dated task titles. If so, update the request text in the integration test fixture to use a day name that is always in the future — e.g. always use "Friday" or "Saturday" in test task titles. Alternatively, configure the test to monkeypatch `datetime.now` to a Monday morning time. The simplest fix: use task titles like "Friday roadmap draft" so the parsed slot is always in the future during a normal work week. Document any test change in your task summary.

7. **Verify no hardcoded dates or UTC hack remain**:
   ```bash
   grep -n "2026, 3, 16" apps/worker/src/helm_worker/jobs/workflow_runs.py  # → no output
   grep -n 'replace.*+00:00' apps/worker/src/helm_worker/jobs/workflow_runs.py  # → no output
   grep -n '_parse_slot_from_title' apps/worker/src/helm_worker/jobs/workflow_runs.py  # → no output
   ```

8. **Run final full check**:
   ```bash
   .venv/bin/python -m pytest tests/unit/ tests/integration/ -v 2>&1 | tail -20
   ```

## Must-Haves

- [ ] `_candidate_slots` no longer references `datetime(2026, 3, 16, ...)` — uses `compute_reference_week(tz)`
- [ ] `_parse_slot_from_title` and duplicate regex constants removed from `workflow_runs.py`
- [ ] `_run_calendar_agent` constructs `tz = ZoneInfo(settings.operator_timezone)` and passes it through
- [ ] `parse_local_slot` called instead of `_parse_slot_from_title`
- [ ] `to_utc` used to convert local slot to UTC before building `ScheduleBlock`
- [ ] `past_event_guard` called before appending each block; raises `PastEventError` → warn-and-skip (not hard exception)
- [ ] `replace("+00:00", "Z")` hack removed from `ScheduleBlock` construction
- [ ] `pytest tests/integration/test_weekly_scheduling_end_to_end.py -v` → passes
- [ ] `pytest tests/integration/ -v` → no regressions
- [ ] `pytest tests/unit/ -v` → no regressions

## Verification

- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && .venv/bin/python -m pytest tests/integration/test_weekly_scheduling_end_to_end.py -v` → all pass
- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && .venv/bin/python -m pytest tests/integration/ -v 2>&1 | tail -10` → no failures
- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && .venv/bin/python -m pytest tests/unit/ -v 2>&1 | tail -10` → no failures
- `grep -n "2026, 3, 16" apps/worker/src/helm_worker/jobs/workflow_runs.py` → no output
- `grep -n 'replace.*+00:00' apps/worker/src/helm_worker/jobs/workflow_runs.py` → no output
- `grep -n '_parse_slot_from_title' apps/worker/src/helm_worker/jobs/workflow_runs.py` → no output (function deleted)

## Observability Impact

- Signals added/changed: `past_event_guard_triggered` warning log fires when a slot is skipped (fields: `task_title`, `reason`); this makes past-event rejection visible in structured logs
- How a future agent inspects this: `grep "past_event_guard_triggered" <log output>` — shows which tasks were rejected and why
- Failure state exposed: if `OPERATOR_TIMEZONE` is unset, `settings.operator_timezone` raises `ValidationError` at `WorkerSettings()` init — surfaces before the job runs

## Inputs

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — the primary change target; lines 329–409 contain the bugs
- `packages/orchestration/src/helm_orchestration/scheduling.py` — T01 output: `compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard`, `PastEventError`
- `apps/worker/src/helm_worker/config.py` — `settings` object with `operator_timezone` field (T02 output)
- `tests/integration/test_weekly_scheduling_end_to_end.py` — regression guard; do not break it; may need minor fixture tweak if past-event guard trips during test run
- `tests/conftest.py` — T02 output; ensures `OPERATOR_TIMEZONE` is set for all tests

## Expected Output

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — refactored: no hardcoded date, no UTC hack, uses shared primitives, warn-and-skip for past events; `_parse_slot_from_title` and duplicate regex constants deleted
- `tests/integration/test_weekly_scheduling_end_to_end.py` — possibly lightly updated task title strings to use future days (if past-event guard trips during test run at certain times of week); no structural test changes
