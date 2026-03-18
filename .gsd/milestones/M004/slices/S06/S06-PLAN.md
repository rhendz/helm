# S06: Dev experience, observability, and cleanup

**Goal:** `milestone/M004` branch (S01–S04) merged into `main` and verified; worker and telegram-bot live-reload on code changes; Datadog logs and APM traces cover the `/task` path; hardcoded scheduling stubs removed; `/agenda` command implemented (missed in S04).

**Demo:** `pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py -q` shows 440+ passed with 0 failures. `scripts/run-worker.sh` and `scripts/run-telegram-bot.sh` use `watchfiles` for auto-reload. `grep -n "2026, 3, 16\|_parse_slot_from_title\|_DAY_OFFSETS\|_TIME_PATTERN" apps/worker/src/helm_worker/jobs/workflow_runs.py` returns nothing.

## Must-Haves

- `milestone/M004` branch merged into `main` with all S01–S04 implementation (LLM inference, `/task`, `/status`, approval policy, proactive notifications, scheduling primitives refactor)
- Merge conflicts resolved correctly: `SyncLookupRequest.calendar_id` retained from `main`; `TaskSemantics` + `WeeklyTaskRequest.urgency/confidence` from `milestone/M004`; E2E conftest safety gates from `main`; `calendar_id` threading from `main`'s `google_calendar.py`; milestone/M004's refactored `workflow_runs.py` with `HELM_CALENDAR_TEST_ID` env var pattern from `main`
- `watchfiles` and `ddtrace` added to dev dependencies; `run-worker.sh` and `run-telegram-bot.sh` use watchfiles-based reload
- `ddtrace` APM spans on `_run_task_async` and the LLM inference call in `task.py`
- Hardcoded date `datetime(2026, 3, 16, 9, ...)`, `_DAY_OFFSETS`, `_TIME_PATTERN`, `_parse_slot_from_title` removed from `workflow_runs.py`
- `/agenda` command implemented: `list_today_events()` on `GoogleCalendarAdapter`, `agenda.py` command handler registered in `main.py`
- 436+ tests pass post-merge with 0 failures (excluding `test_study_agent_mvp`)

## Proof Level

- This slice proves: final-assembly
- Real runtime required: no (merge verified by test suite; live reload and Datadog are operational checks)
- Human/UAT required: yes (live reload visual confirmation; `/agenda` via real Telegram)

## Verification

- `uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py -q` → 440+ passed, 0 failures
- `grep -n "2026, 3, 16\|_parse_slot_from_title\|_DAY_OFFSETS\|_TIME_PATTERN" apps/worker/src/helm_worker/jobs/workflow_runs.py` → no output
- `grep -rn 'calendarId="primary"' packages/connectors/src/helm_connectors/google_calendar.py` → no output
- `grep "watchfiles" pyproject.toml` → present in dev deps
- `grep "ddtrace" pyproject.toml` → present in dev deps
- `grep "watchfiles" scripts/run-worker.sh scripts/run-telegram-bot.sh` → both scripts reference watchfiles
- `python -c "from helm_telegram_bot.commands import agenda"` → import succeeds (with PYTHONPATH)
- `uv run --frozen pytest tests/unit/test_agenda_command.py -v` → passed

## Observability / Diagnostics

- Runtime signals: `ddtrace` spans on `helm.task.run` and `helm.task.inference` (no-op without DD agent); existing structlog JSON logs are DD-compatible
- Inspection surfaces: `DD_ENV`, `DD_SERVICE`, `DD_VERSION` in `.env.example` for DD agent configuration
- Failure visibility: `ddtrace` spans include error tags on exception; structlog events `task_inference_complete` / `task_inference_failed` include run_id
- Redaction constraints: none (no secrets in traces)

## Integration Closure

- Upstream surfaces consumed: `milestone/M004` branch (S01–S04 implementation), `main` branch (S05 test infrastructure + calendar_id threading)
- New wiring introduced in this slice: `/agenda` command handler registration in `main.py`; watchfiles-based reload in shell scripts; `ddtrace` spans in `task.py`
- What remains before the milestone is truly usable end-to-end: nothing — S06 is the final assembly slice

## Tasks

- [x] **T01: Merge milestone/M004 into main and verify full test suite** `est:1h`
  - Why: Nothing from S01–S04 is deployable until the milestone branch is merged into main. This is the critical path for the entire milestone.
  - Files: All files modified on `milestone/M004` (see research); key conflicts in `schemas.py`, `__init__.py`, `google_calendar.py`, `workflow_runs.py`, `e2e/conftest.py`, `test_workflow_telegram_commands.py`
  - Do: Merge `milestone/M004` into `main`. Resolve conflicts per documented rules: (1) `schemas.py` — keep `SyncLookupRequest.calendar_id` from main + add `TaskSemantics`/`WeeklyTaskRequest.urgency,confidence` from milestone; (2) `google_calendar.py` — keep main's `calendar_id` threading; (3) `e2e/conftest.py` — keep main's safety gates; (4) `workflow_runs.py` — take milestone's refactored structure but ensure `_run_calendar_agent` uses `os.getenv("HELM_CALENDAR_TEST_ID", "primary")` for calendar_id; (5) `__init__.py` — merge `__all__` entries keeping all symbols; (6) `test_workflow_telegram_commands.py` — take milestone's version with `execute_after_approval` assertions; (7) `.gsd/` docs — take main's versions. Ensure `tests/conftest.py` exists (from milestone — sets `OPERATOR_TIMEZONE`). Delete `tests/integration/test_google_calendar_adapter_real_api.py` if conflict (main moved it to unit/).
  - Verify: `uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py -q` → 440+ passed, 0 failures
  - Done when: All S01–S04 implementation is on `main`, full test suite passes with 0 failures

- [x] **T02: Add watchfiles live reload and ddtrace APM instrumentation** `est:30m`
  - Why: R116 requires live reload for worker/bot dev loop; R117 requires Datadog observability on the `/task` path. Both are additive and share the pyproject.toml edit.
  - Files: `pyproject.toml`, `scripts/run-worker.sh`, `scripts/run-telegram-bot.sh`, `apps/telegram-bot/src/helm_telegram_bot/commands/task.py`, `.env.example`
  - Do: (1) Add `watchfiles>=0.21.0` and `ddtrace>=2.0.0` to `[project.optional-dependencies].dev` in pyproject.toml. (2) Update `run-worker.sh` to use `python -m watchfiles --filter python helm_worker.main apps/worker/src packages/`. (3) Same for `run-telegram-bot.sh` with `helm_telegram_bot.main apps/telegram-bot/src packages/`. (4) In `task.py`, wrap `_run_task_async` body with `ddtrace` span `helm.task.run` and wrap the `run_in_executor` LLM call with span `helm.task.inference`. Import `tracer` at top. (5) Add `DD_ENV`, `DD_SERVICE`, `DD_VERSION` to `.env.example`.
  - Verify: `grep "watchfiles" scripts/run-worker.sh scripts/run-telegram-bot.sh` → both match; `grep "ddtrace" pyproject.toml` → present; `python -c "from ddtrace import tracer"` or best-effort (package may not be installed in test env)
  - Done when: Both scripts use watchfiles; ddtrace spans are in task.py; dev deps updated

- [ ] **T03: Remove legacy stubs and implement /agenda command** `est:45m`
  - Why: R118 requires removal of hardcoded scheduling stubs post-refactor. The `/agenda` command (R109) was described in S04 roadmap but never committed — it's the one net-new feature gap. Combining these because cleanup is a verification + small edit, and `/agenda` is a focused addition.
  - Files: `apps/worker/src/helm_worker/jobs/workflow_runs.py`, `packages/orchestration/src/helm_orchestration/scheduling.py`, `packages/connectors/src/helm_connectors/google_calendar.py`, `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py` (new), `apps/telegram-bot/src/helm_telegram_bot/main.py`, `tests/unit/test_agenda_command.py` (new)
  - Do: (1) In `workflow_runs.py`, verify and remove `_DAY_OFFSETS`, `_TIME_PATTERN`, `_parse_slot_from_title`, and the hardcoded `datetime(2026, 3, 16, 9, ...)` if still present post-merge. Keep `_RANGE_PATTERN` (used by `_parse_duration_from_title`). (2) In `scheduling.py`, remove "S01 stub" comment from `ConditionalApprovalPolicy`. (3) Add `list_today_events(calendar_id: str, timezone: ZoneInfo) -> list[dict]` to `GoogleCalendarAdapter` — calls `events().list()` with `timeMin`/`timeMax` for today in operator local time. (4) Create `agenda.py` command: auth guard → get adapter → call `list_today_events` → format events in local time → reply (handle empty "No events today"). (5) Register `CommandHandler("agenda", agenda.handle)` in `main.py`. (6) Write `tests/unit/test_agenda_command.py` testing: events formatting, empty-day response, auth rejection.
  - Verify: `grep -n "2026, 3, 16\|_parse_slot_from_title\|_DAY_OFFSETS\|_TIME_PATTERN" apps/worker/src/helm_worker/jobs/workflow_runs.py` → no output; `uv run --frozen pytest tests/unit/test_agenda_command.py -v` → passed; full suite still passes
  - Done when: No legacy stubs in workflow_runs.py; `/agenda` command exists, registered, and tested

## Files Likely Touched

- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/__init__.py`
- `packages/orchestration/src/helm_orchestration/scheduling.py`
- `packages/connectors/src/helm_connectors/google_calendar.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py` (new)
- `apps/telegram-bot/src/helm_telegram_bot/commands/status.py` (from merge)
- `apps/telegram-bot/src/helm_telegram_bot/main.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` (from merge)
- `tests/conftest.py` (from merge)
- `tests/e2e/conftest.py`
- `tests/unit/test_agenda_command.py` (new)
- `tests/unit/test_workflow_telegram_commands.py`
- `pyproject.toml`
- `scripts/run-worker.sh`
- `scripts/run-telegram-bot.sh`
- `.env.example`
