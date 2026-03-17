# S02: Timezone correctness and shared scheduling primitives

**Goal:** Replace the hardcoded `datetime(2026, 3, 16, 9, tzinfo=UTC)` in `_candidate_slots` with dynamic timezone-aware scheduling primitives; add `OPERATOR_TIMEZONE` as required config; wire the corrected primitives into the worker job so the weekly workflow schedules at the correct local time.
**Demo:** `compute_reference_week(ZoneInfo("America/Los_Angeles"))` returns this Monday at midnight PDT; `parse_local_slot("Monday deep work 10am", week_start, tz)` returns `hour=10` in PDT; `past_event_guard` raises on past datetimes; the full integration suite (`pytest tests/integration/test_weekly_scheduling_end_to_end.py`) passes unchanged.

## Must-Haves

- `scheduling.py` exports `compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard` as pure functions
- `OPERATOR_TIMEZONE` is a required field on `RuntimeAppSettings`; startup raises `ValidationError` if absent or `ZoneInfoNotFoundError` if invalid IANA string
- `_candidate_slots` and `_parse_slot_from_title` in `workflow_runs.py` delegate to the shared primitives and use operator local time, not hardcoded UTC
- The `replace("+00:00", "Z")` hack in `_run_calendar_agent` is removed; `ScheduleBlock.start`/`.end` emit proper RFC3339 with timezone offset
- `past_event_guard` is called before appending to `scheduled_blocks` in `_run_calendar_agent`; past slots warn-and-skip (not hard crash)
- All prior integration tests still pass (`pytest tests/integration/ -v`)
- New unit tests in `tests/unit/test_scheduling_primitives.py` cover all four primitives

## Proof Level

- This slice proves: contract + integration
- Real runtime required: no (unit tests for primitives; integration tests use in-memory SQLite)
- Human/UAT required: no

## Verification

- `pytest tests/unit/test_scheduling_primitives.py -v` — all new primitive tests pass
- `pytest tests/unit/test_task_inference.py -v` — existing S01 tests unchanged (no regression to `ConditionalApprovalPolicy.evaluate`)
- `pytest tests/integration/test_weekly_scheduling_end_to_end.py -v` — full regression check for weekly workflow path
- `pytest tests/integration/ -v` — broader integration regression
- `pytest tests/unit/ -v` — no unit test failures introduced by `OPERATOR_TIMEZONE` config change
- Functional check: `python -c "from helm_orchestration import compute_reference_week, parse_local_slot, to_utc, past_event_guard; print('imports ok')"` exits 0
- Functional check: `from helm_orchestration.scheduling import compute_reference_week; from zoneinfo import ZoneInfo; w = compute_reference_week(ZoneInfo('America/Los_Angeles')); assert w.tzinfo is not None and w.weekday() == 0`

## Observability / Diagnostics

- Runtime signals: structlog `past_event_guard_triggered` warning when a slot is skipped; `scheduling_primitives_invoked` debug log with `tz`, `week_start`, and computed slot count on each calendar-agent run
- Inspection surfaces: `OPERATOR_TIMEZONE` value is echoed in worker startup log; visible in `WorkerSettings` at import time
- Failure visibility: `ValidationError` at startup if `OPERATOR_TIMEZONE` unset; `ZoneInfoNotFoundError` if invalid — both surface before the first job runs
- Redaction constraints: none — timezone strings are not sensitive

## Integration Closure

- Upstream surfaces consumed: `scheduling.py` (S01-created, `ApprovalPolicy` + `ConditionalApprovalPolicy`); `schemas.py` (`CalendarAgentInput`, `ScheduleBlock`); `workflow_runs.py` (`_candidate_slots`, `_parse_slot_from_title`, `_run_calendar_agent`); `config.py` (`RuntimeAppSettings`)
- New wiring introduced in this slice: `workflow_runs.py` imports `compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard` from `helm_orchestration`; imports `ZoneInfo` and reads `settings.operator_timezone` at job call time
- What remains before the milestone is truly usable end-to-end: S03 (inline execution path for `/task`), S04 (Telegram UX / proactive notifications), S05 (real E2E calendar assertions)

## Tasks

- [ ] **T01: Add timezone primitives to scheduling.py and unit-test them** `est:45m`
  - Why: The four pure functions (`compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard`) are the foundation everything else delegates to. Implementing and unit-testing them in isolation — before touching the worker or config — keeps the complex timezone logic reviewable and verifiable independently.
  - Files: `packages/orchestration/src/helm_orchestration/scheduling.py`, `packages/orchestration/src/helm_orchestration/__init__.py`, `tests/unit/test_scheduling_primitives.py`
  - Do: Add four pure functions to `scheduling.py` (below the existing `ConditionalApprovalPolicy`); export them from `__init__.py`; write `test_scheduling_primitives.py` with ≥12 assertions covering all four functions and failure paths
  - Verify: `pytest tests/unit/test_scheduling_primitives.py -v` → all pass; `pytest tests/unit/test_task_inference.py -v` → still passes (no regression)
  - Done when: all new primitive tests pass and existing S01 unit tests are unaffected

- [ ] **T02: Add OPERATOR_TIMEZONE to RuntimeAppSettings and fix test environment** `est:30m`
  - Why: `OPERATOR_TIMEZONE` must be required config with fail-fast validation before any scheduling work runs. Adding it as a required field on `RuntimeAppSettings` will break any unit/integration test that instantiates a settings subclass without the env var — a `conftest.py` at `tests/` level is the cleanest fix.
  - Files: `packages/runtime/src/helm_runtime/config.py`, `tests/conftest.py` (new), `.env.example`
  - Do: Add `operator_timezone: str` field with a `field_validator` that calls `ZoneInfo(value)` to validate at init; create `tests/conftest.py` autouse fixture that sets `OPERATOR_TIMEZONE=America/Los_Angeles` for all tests; add the var to `.env.example`
  - Verify: `pytest tests/unit/ -v` → no failures caused by missing `OPERATOR_TIMEZONE`; `python -c "import os; os.environ['OPERATOR_TIMEZONE']='Bad/Zone'; from helm_runtime.config import RuntimeAppSettings"` then construct instance and confirm it raises
  - Done when: all unit tests pass; invalid IANA string raises at `RuntimeAppSettings` init; `OPERATOR_TIMEZONE` is visible in `.env.example`

- [ ] **T03: Refactor workflow_runs.py to use shared primitives and fix RFC3339** `est:60m`
  - Why: This task closes the actual bug — replacing `datetime(2026, 3, 16, 9, tzinfo=UTC)` with `compute_reference_week`, wiring `parse_local_slot` and `to_utc` for correct local-time interpretation, removing the `replace("+00:00", "Z")` hack, and adding the `past_event_guard` call before each `ScheduleBlock` is appended. This is the integration closure step — verified by the regression suite.
  - Files: `apps/worker/src/helm_worker/jobs/workflow_runs.py`
  - Do: Replace `_candidate_slots` body to call `compute_reference_week(tz)` and generate slots relative to it; update `_run_calendar_agent` to read `settings.operator_timezone` and pass `ZoneInfo(...)` through; replace `_parse_slot_from_title` with `parse_local_slot`; fix RFC3339 output; add `past_event_guard` warn-and-skip; run full integration suite
  - Verify: `pytest tests/integration/test_weekly_scheduling_end_to_end.py -v` → passes; `pytest tests/integration/ -v` → no regressions; `grep "2026, 3, 16" apps/worker/src/helm_worker/jobs/workflow_runs.py` → no matches; `grep 'replace.*+00:00' apps/worker/src/helm_worker/jobs/workflow_runs.py` → no matches
  - Done when: no hardcoded date, no UTC hack, past-event guard in place, full integration suite green

## Files Likely Touched

- `packages/orchestration/src/helm_orchestration/scheduling.py`
- `packages/orchestration/src/helm_orchestration/__init__.py`
- `packages/runtime/src/helm_runtime/config.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `tests/unit/test_scheduling_primitives.py` (new)
- `tests/conftest.py` (new)
- `.env.example`
