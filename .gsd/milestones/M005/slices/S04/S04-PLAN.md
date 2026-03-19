# S04: Replace Calendar Connector in Worker + Bot

**Goal:** `workflow_runs.py` and `agenda.py` use `GoogleCalendarProvider`; `packages/connectors/google_calendar.py` deleted; `/agenda` shows real events via MCP.
**Demo:** `rg "GoogleCalendarAdapter\|GoogleCalendarAuth" apps/ tests/` returns 0 results (excluding e2e/); `uv run pytest tests/unit/test_agenda_command.py -v` passes 4 tests; all integration tests that construct `WorkflowStatusService` still pass.

## Must-Haves

- `agenda.py` constructs `GoogleCalendarProvider(user_id, db)` via `SessionLocal` + `get_user_by_telegram_id`, matching the pattern in `task.py`
- `apps/api/services/workflow_status_service.py` replaces `GoogleCalendarAdapter(auth)` with `GoogleCalendarProvider(user_id, session)`, keeping `StubCalendarSystemAdapter` fallback for tests
- `packages/connectors/google_calendar.py` deleted; `__init__.py` updated (no `GoogleCalendarAdapter`/`GoogleCalendarAuth` exports)
- `test_agenda_command.py` rewritten to monkeypatch `GoogleCalendarProvider` instead of `GoogleCalendarAdapter`
- `test_google_calendar_adapter.py` and `test_google_calendar_auth.py` deleted
- Integration tests with `GoogleCalendarAdapter(auth)` real-credential blocks rewritten to use `GoogleCalendarProvider`
- All existing test_agenda_command behavioral assertions (events shown, empty day, unauthorized, all-day) survive unchanged

## Proof Level

- This slice proves: integration (connector fully replaced in all non-e2e source and test paths)
- Real runtime required: no (real Google API calls are UAT scope; contract proof via unit/integration tests)
- Human/UAT required: no (deferred to M005 final assembly)

## Verification

- `rg "GoogleCalendarAdapter\|GoogleCalendarAuth" apps/ tests/unit/ tests/integration/ -t py` → 0 results
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c "import helm_telegram_bot.commands.agenda; print('ok')"` → ok
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run python -c "import helm_api.services.workflow_status_service; print('ok')"` → ok
- `uv run pytest tests/unit/test_agenda_command.py -v` → 4 passed
- `uv run pytest tests/integration/test_weekly_scheduling_end_to_end.py tests/integration/test_weekly_scheduling_with_drift_recovery.py tests/integration/test_drift_recovery_actions_in_workflow_status.py tests/integration/test_drift_recovery_workflows.py tests/integration/test_drift_detection_and_reconciliation.py tests/integration/test_workflow_status_routes.py -v` → all pass
- `ls packages/connectors/src/helm_connectors/google_calendar.py` → file not found
- `uv run ruff check apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py apps/api/src/helm_api/services/workflow_status_service.py` → 0 errors

## Observability / Diagnostics

- Runtime signals: structlog `list_today_events` / `list_today_events_complete` events (from `GoogleCalendarProvider`) now fire from `/agenda`; `calendar_provider_constructed` event (not present — agenda constructs inline, no wrapper helper) — but the provider's internal log events propagate
- Inspection surfaces: `OPERATOR_TIMEZONE` in `/agenda` output header; `GoogleCalendarProvider` structlog events
- Failure visibility: `RuntimeError("No Helm user found...")` in agenda handler when no user row; `StubCalendarSystemAdapter` fallback in API `WorkflowStatusService` when user lookup fails — both are clean, non-silent error paths
- Redaction constraints: no secrets in log fields (provider uses user_id only, per S02 credentials.py contract)

## Integration Closure

- Upstream surfaces consumed: `GoogleCalendarProvider` from `packages/providers` (S02); `get_user_by_telegram_id` from `packages/storage` (S01); `SessionLocal` from `packages/storage` (S01)
- New wiring introduced in this slice: `agenda.py` now opens a `SessionLocal` context + user lookup (same as `task.py`); `api/services/workflow_status_service.py` constructor does user lookup via `TELEGRAM_ALLOWED_USER_ID` env var
- What remains before the milestone is truly usable end-to-end: S05 (Gmail connector replacement), S06 (delete `packages/connectors/` entirely, finalize protocols)

## Tasks

- [x] **T01: Migrate agenda.py + API workflow_status_service.py to GoogleCalendarProvider; delete google_calendar.py; rewrite test_agenda_command.py** `est:40m`
  - Why: Eliminates all `GoogleCalendarAdapter`/`GoogleCalendarAuth` usage from production source files and the agenda unit test; deletes the bespoke calendar connector module.
  - Files: `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py`, `apps/api/src/helm_api/services/workflow_status_service.py`, `packages/connectors/src/helm_connectors/__init__.py`, `packages/connectors/src/helm_connectors/google_calendar.py`, `tests/unit/test_agenda_command.py`, `tests/unit/test_google_calendar_adapter.py`, `tests/unit/test_google_calendar_auth.py`
  - Do: (1) Rewrite `agenda.py` following `task.py` pattern: import `SessionLocal`, `get_user_by_telegram_id`, `GoogleCalendarProvider`; open DB session; resolve user from `update.effective_user.id`; construct provider; call `list_today_events`. (2) Rewrite `api/services/workflow_status_service.py` constructor: replace `GoogleCalendarAdapter(auth)` try/except with `GoogleCalendarProvider(user_id, session)` lookup via `TELEGRAM_ALLOWED_USER_ID` + `get_user_by_telegram_id`; keep `StubCalendarSystemAdapter` fallback. Remove `GoogleCalendarAdapter`/`GoogleCalendarAuth` imports, keep `StubCalendarSystemAdapter`/`StubTaskSystemAdapter`. (3) Delete `packages/connectors/src/helm_connectors/google_calendar.py`. (4) Update `packages/connectors/src/helm_connectors/__init__.py` to remove deleted exports. (5) Rewrite `test_agenda_command.py` to monkeypatch `GoogleCalendarProvider`/`SessionLocal`/`get_user_by_telegram_id` instead of old adapter. (6) Delete `test_google_calendar_adapter.py` and `test_google_calendar_auth.py`.
  - Verify: `uv run pytest tests/unit/test_agenda_command.py -v` → 4 passed; `rg "GoogleCalendarAdapter\|GoogleCalendarAuth" apps/ tests/unit/ -t py` → 0 results; import checks pass for both modules; ruff clean.
  - Done when: No production source or unit test file references `GoogleCalendarAdapter` or `GoogleCalendarAuth`; `google_calendar.py` deleted from connectors; all 4 agenda tests pass.

- [x] **T02: Rewrite integration tests that use GoogleCalendarAdapter in real-credential blocks** `est:30m`
  - Why: `test_weekly_scheduling_end_to_end.py` and `test_weekly_scheduling_with_drift_recovery.py` have `HELM_E2E` guarded blocks that construct `GoogleCalendarAdapter(auth)`. These must be updated to `GoogleCalendarProvider(user_id, session)` with seeded `UserCredentialsORM` rows. Other integration tests that only use stubs must still pass with the updated `WorkflowStatusService` constructor.
  - Files: `tests/integration/test_weekly_scheduling_end_to_end.py`, `tests/integration/test_weekly_scheduling_with_drift_recovery.py`
  - Do: (1) In `test_weekly_scheduling_end_to_end.py`: replace `GoogleCalendarAdapter(auth)` real-credentials block with `GoogleCalendarProvider(user_id, session)` using `_seed_test_user()` pattern from `test_task_execution_integration.py`. Remove `GoogleCalendarAdapter`/`GoogleCalendarAuth` imports. (2) Same treatment for `test_weekly_scheduling_with_drift_recovery.py` — all 4+ blocks that construct `GoogleCalendarAdapter(auth)`. Add `_seed_test_user()` helper; seed `UserORM` + `UserCredentialsORM`; use `GoogleCalendarProvider(user_id, session)`. (3) Run all integration tests to confirm stub-only tests still pass (the updated `WorkflowStatusService` falls back to `StubCalendarSystemAdapter` when no user row exists).
  - Verify: `uv run pytest tests/integration/test_weekly_scheduling_end_to_end.py tests/integration/test_weekly_scheduling_with_drift_recovery.py tests/integration/test_drift_recovery_actions_in_workflow_status.py tests/integration/test_drift_recovery_workflows.py tests/integration/test_drift_detection_and_reconciliation.py tests/integration/test_workflow_status_routes.py -v` → all pass; `rg "GoogleCalendarAdapter\|GoogleCalendarAuth" tests/integration/ -t py` → 0 results.
  - Done when: Zero `GoogleCalendarAdapter`/`GoogleCalendarAuth` references in `tests/integration/`; all integration tests pass.

## Files Likely Touched

- `apps/telegram-bot/src/helm_telegram_bot/commands/agenda.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `packages/connectors/src/helm_connectors/__init__.py`
- `packages/connectors/src/helm_connectors/google_calendar.py` (deleted)
- `tests/unit/test_agenda_command.py`
- `tests/unit/test_google_calendar_adapter.py` (deleted)
- `tests/unit/test_google_calendar_auth.py` (deleted)
- `tests/integration/test_weekly_scheduling_end_to_end.py`
- `tests/integration/test_weekly_scheduling_with_drift_recovery.py`
