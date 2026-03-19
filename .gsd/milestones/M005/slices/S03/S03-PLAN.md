# S03: Unified /task Pipeline

**Goal:** `/task` and `/workflow_start` both use `GoogleCalendarProvider` for calendar operations instead of the bespoke `_build_calendar_adapter()` path that reaches into `helm_connectors.google_calendar`.

**Demo:** `execute_task_run` and `execute_after_approval` construct a `GoogleCalendarProvider(user_id, db)` using the bootstrap user looked up from the run's `submitted_by` field; the worker recovery path (`_build_resume_service`) does the same using `TELEGRAM_ALLOWED_USER_ID`; `rg "helm_connectors.google_calendar" apps/` returns zero hits; all existing unit and integration tests pass.

## Must-Haves

- `workflow_status_service.py` constructs `GoogleCalendarProvider(user_id, db)` instead of calling `_build_calendar_adapter()`
- `workflow_runs.py` replaces `_build_calendar_adapter()` with a `GoogleCalendarProvider`-based construction; `GoogleCalendarAdapter` and `GoogleCalendarAuth` imports removed
- User lookup from `submitted_by` field (format `"telegram:{id}"`) threads into provider construction
- Worker recovery path resolves bootstrap user via `TELEGRAM_ALLOWED_USER_ID` env var (V1 single-user)
- `_build_calendar_adapter()` function is deleted from `workflow_runs.py`
- Integration test (`test_task_execution_integration.py`) passes with provider patched (no real Google calls)
- Unit tests (`test_task_execution.py`) continue to pass
- `StubTaskSystemAdapter` import from `helm_connectors` remains (S06 scope) — only calendar adapter references are removed

## Proof Level

- This slice proves: integration (provider wiring through the full /task state machine)
- Real runtime required: no (stubbed in tests; real runtime is S04 UAT)
- Human/UAT required: no

## Verification

- `uv run pytest tests/unit/test_task_execution.py -v` — all 10 tests pass
- `uv run pytest tests/integration/test_task_execution_integration.py -v` — full state-machine test passes
- `rg "helm_connectors.google_calendar" apps/telegram-bot/src/ apps/worker/src/ -t py` — zero results
- `rg "_build_calendar_adapter" apps/ -t py` — zero results (function deleted)
- `python -c "import helm_telegram_bot.services.workflow_status_service; print('ok')"` — no import errors
- `python -c "import helm_worker.jobs.workflow_runs; print('ok')"` — no import errors
- `uv run ruff check apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py apps/worker/src/helm_worker/jobs/workflow_runs.py` — zero errors

## Observability / Diagnostics

- Runtime signals: structlog `calendar_provider_constructed` (info, fields: user_id, source) when provider is built; existing `calendar_upsert_*` signals from `GoogleCalendarProvider` propagate unchanged
- Failure visibility: `RuntimeError("No user found for telegram_id=...")` or `RuntimeError("No Google credentials for user_id=...")` — clear error surface replacing the silent stub fallback
- Redaction constraints: user credentials never logged (enforced by `GoogleCalendarProvider` and `build_google_credentials`)

## Integration Closure

- Upstream surfaces consumed: `GoogleCalendarProvider` from `helm_providers` (S02); `get_user_by_telegram_id` from `helm_storage.repositories` (S01); `StubTaskSystemAdapter` from `helm_connectors` (unchanged, deletion is S06)
- New wiring introduced: user lookup from `submitted_by` → `GoogleCalendarProvider` construction in both inline and worker paths
- What remains: S04 replaces `agenda.py` connector usage; S05 replaces Gmail connector; S06 deletes `packages/connectors/`

## Tasks

- [x] **T01: Replace _build_calendar_adapter with GoogleCalendarProvider in both execution paths** `est:40m`
  - Why: The core deliverable — swap bespoke connector for MCP-backed provider in the two files that construct the calendar adapter for `/task` pipeline execution
  - Files: `apps/worker/src/helm_worker/jobs/workflow_runs.py`, `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
  - Do: (1) In `workflow_runs.py`: remove `GoogleCalendarAdapter`/`GoogleCalendarAuth` imports from `helm_connectors.google_calendar`; add `from helm_providers import GoogleCalendarProvider` and `from helm_storage.repositories.users import get_user_by_telegram_id`; delete `_build_calendar_adapter()` function; create `_build_calendar_provider(db, user_id)` that returns `GoogleCalendarProvider(user_id, db)`; update `_build_resume_service` to accept `user_id` param and use new provider helper; add a `_resolve_bootstrap_user_id(db)` helper for the worker path that looks up the user via `TELEGRAM_ALLOWED_USER_ID` env var. (2) In `workflow_status_service.py`: remove lazy import of `_build_calendar_adapter` from `workflow_runs`; add top-level `from helm_providers import GoogleCalendarProvider` and `from helm_storage.repositories.users import get_user_by_telegram_id`; add `_parse_telegram_user_id(submitted_by)` helper to extract telegram ID from `"telegram:{id}"` format; in `execute_task_run`, look up user inside `SessionLocal()` block and construct `GoogleCalendarProvider(user.id, session)`; in `execute_after_approval`, fetch the run to get `submitted_by`, parse telegram ID, look up user, pass `user_id` into `_build_resume_service`. (3) Add TODO comment in `_resolve_bootstrap_user_id` noting V1 single-user limitation.
  - Verify: `python -c "import helm_telegram_bot.services.workflow_status_service; print('ok')"` and `python -c "import helm_worker.jobs.workflow_runs; print('ok')"` both succeed; `rg "_build_calendar_adapter" apps/ -t py` returns 0 results; `rg "helm_connectors.google_calendar" apps/telegram-bot/src/ apps/worker/src/ -t py` returns 0 results; `uv run ruff check apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py apps/worker/src/helm_worker/jobs/workflow_runs.py` passes
  - Done when: Both files import `GoogleCalendarProvider` from `helm_providers`, construct it with `user_id` + `db`, and have zero references to `_build_calendar_adapter` or `helm_connectors.google_calendar`

- [x] **T02: Update integration and unit tests for provider-swapped pipeline** `est:30m`
  - Why: The integration test currently relies on `_build_calendar_adapter`'s stub fallback (no Google credentials → `StubCalendarSystemAdapter`). After T01 deletes that function, the test will fail because `GoogleCalendarProvider.__init__` calls `get_credentials()` which returns `None` on the test's in-memory DB (no user row seeded). The unit tests mock at the service level and should mostly pass, but any that reference `_build_calendar_adapter` need updating.
  - Files: `tests/integration/test_task_execution_integration.py`, `tests/unit/test_task_execution.py`
  - Do: (1) In `test_task_execution_integration.py`: seed a bootstrap user + credentials row in the in-memory SQLite session (use `UserORM` and `UserCredentialsORM` from `helm_storage.models`); patch `GoogleCalendarProvider` at `helm_providers.google_calendar.GoogleCalendarProvider` to return a `StubCalendarSystemAdapter()` instance (which satisfies the protocol structurally); remove the `_mock_patch("google.oauth2.credentials.Credentials")` and `_mock_patch("googleapiclient.discovery.build")` guards that were working around the old adapter path; update docstring to reflect provider-based architecture. (2) In `test_task_execution.py`: verify tests 6–10 still pass (they use `_build_specialist_steps` and `_run_task_inference` from `workflow_runs` — these should be unaffected since they don't touch `_build_calendar_adapter`); if any test patches `_build_calendar_adapter`, update the patch target. (3) Run full verification suite.
  - Verify: `uv run pytest tests/unit/test_task_execution.py -v` — all pass; `uv run pytest tests/integration/test_task_execution_integration.py -v` — passes; `uv run ruff check tests/integration/test_task_execution_integration.py tests/unit/test_task_execution.py` — zero errors
  - Done when: Both test files pass with zero references to `_build_calendar_adapter`; integration test seeds a user row and patches the provider constructor

## Files Likely Touched

- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `tests/integration/test_task_execution_integration.py`
- `tests/unit/test_task_execution.py`
