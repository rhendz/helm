---
estimated_steps: 5
estimated_files: 2
---

# T02: Update integration and unit tests for provider-swapped pipeline

**Slice:** S03 — Unified /task Pipeline
**Milestone:** M005

## Description

After T01 replaces `_build_calendar_adapter()` with `GoogleCalendarProvider` construction, two test files need updates:

1. **`test_task_execution_integration.py`** — currently relies on `_build_calendar_adapter()`'s silent stub fallback (when Google credentials are absent from env, it returns `StubCalendarSystemAdapter`). After T01, the provider constructor calls `get_credentials(user_id, "google", db)` on the test's in-memory SQLite session. Since no user row exists, this returns `None` and raises `RuntimeError`. The test must: (a) seed a bootstrap user + credentials row, and (b) patch `GoogleCalendarProvider` to avoid making real Google API calls.

2. **`test_task_execution.py`** — unit tests that mock at the service level (using `_FakeService` and `_FakeWorkflowService`). Tests 1–5 and 8–9 should pass unchanged since they mock the entire service. Tests 6–7 (`test_build_specialist_steps_includes_task_quick_add`, `test_run_task_inference_produces_calendar_agent_output`) and test 10 import from `workflow_runs` directly — verify they still pass since they don't touch `_build_calendar_adapter`.

**Key constraints:**
- The integration test uses an in-memory SQLite session with `Base.metadata.create_all()`. This creates all tables including `users` and `user_credentials` (added in S01).
- The `StubCalendarSystemAdapter` from `helm_connectors` is still available (not deleted until S06). Use it as the mock replacement for `GoogleCalendarProvider`.
- The integration test patches `SessionLocal` everywhere to share a single in-memory session. The `GoogleCalendarProvider` constructor would be called inside these patched session blocks — so patching the constructor class itself is the cleanest approach.
- Tests should NOT depend on `TELEGRAM_ALLOWED_USER_ID` being set in the test environment.

**Available skill:** `test` — use for running and verifying tests.

## Steps

1. **Edit `tests/integration/test_task_execution_integration.py`**:
   - Add imports: `from helm_storage.models import UserORM, UserCredentialsORM`
   - Add a helper function `_seed_bootstrap_user(session: Session) -> UserORM` that:
     - Creates a `UserORM` row with `telegram_user_id=42` (matching the test's `submitted_by="test-user"` — but wait, the test uses `submitted_by="test-user"`, not `submitted_by="telegram:42"`). The `_resolve_user_id` helper in T01 falls back to `TELEGRAM_ALLOWED_USER_ID` env var when `submitted_by` doesn't start with `"telegram:"`. So: set `monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")` in the test, and seed a user with `telegram_user_id=42`.
     - Creates a `UserCredentialsORM` row with `user_id=user.id`, `provider="google"`, `email="test@example.com"`, `refresh_token="fake-refresh-token"`, `client_id="fake-client-id"`, `client_secret="fake-client-secret"`, `scopes="https://www.googleapis.com/auth/calendar"`
     - Flushes (not commits) the session so the rows are visible in the same transaction
     - Returns the user
   - In `test_task_execution_creates_blocked_run_and_completes_after_approval`:
     - After `_make_session()`, call `_seed_bootstrap_user(session)` 
     - Set `monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")` so `_resolve_user_id` can find the bootstrap user via env var fallback
     - Patch `GoogleCalendarProvider` at its import location: `monkeypatch.setattr("helm_providers.google_calendar.GoogleCalendarProvider", lambda user_id, db: StubCalendarSystemAdapter())` — this makes any code that constructs `GoogleCalendarProvider(user_id, db)` get a `StubCalendarSystemAdapter` instead
     - Also need to import `StubCalendarSystemAdapter` from `helm_connectors` in the test file
     - Remove the two `_mock_patch("google.oauth2.credentials.Credentials")` / `_mock_patch("googleapiclient.discovery.build")` context manager blocks from Steps 2 and 4 — they were working around the old adapter path and are no longer needed with the provider patched
     - Update the docstring to reflect that the test now patches `GoogleCalendarProvider` rather than relying on credential-absent stub fallback
   - Also need to patch `GoogleCalendarProvider` at the import sites in both modules:
     - `monkeypatch.setattr("helm_telegram_bot.services.workflow_status_service.GoogleCalendarProvider", lambda user_id, db: StubCalendarSystemAdapter())`
     - `monkeypatch.setattr("helm_worker.jobs.workflow_runs.GoogleCalendarProvider", lambda user_id, db: StubCalendarSystemAdapter())`
     - (The monkeypatch on the module-level name is more reliable than patching the source module, since each importing module gets its own reference)

2. **Verify `tests/unit/test_task_execution.py`**:
   - Run the full unit test file: `uv run pytest tests/unit/test_task_execution.py -v`
   - Tests 1–5, 8–9 mock at the service level (`_FakeService`, `_FakeWorkflowService`) and should pass unchanged
   - Tests 6, 7, 10 import `_build_specialist_steps` and `_run_task_inference` from `workflow_runs` — these functions don't call `_build_calendar_adapter` (they're specialist step handlers), so they should pass unchanged
   - If any test patches `_build_calendar_adapter` by name, update the patch target. Based on review, none of the 10 tests reference `_build_calendar_adapter` directly — they all mock at a higher level.

3. **Verify no remaining references to deleted function**:
   - `rg "_build_calendar_adapter" tests/ -t py` — should return zero results (only the docstring comment may reference it; that's fine if it's updated)

4. **Run ruff on test files**:
   - `uv run ruff check tests/integration/test_task_execution_integration.py tests/unit/test_task_execution.py`

5. **Run full verification**:
   - `uv run pytest tests/unit/test_task_execution.py -v` — all 10 pass
   - `uv run pytest tests/integration/test_task_execution_integration.py -v` — passes
   - `uv run ruff check tests/integration/test_task_execution_integration.py` — zero errors

## Must-Haves

- [ ] Integration test seeds a `UserORM` + `UserCredentialsORM` row in the in-memory session
- [ ] `GoogleCalendarProvider` is patched in the integration test (no real Google API calls)
- [ ] `TELEGRAM_ALLOWED_USER_ID` env var is set in the integration test for user resolution fallback
- [ ] The old `_mock_patch("google.oauth2.credentials.Credentials")` / `_mock_patch("googleapiclient.discovery.build")` guards are removed
- [ ] All 10 unit tests pass unchanged (or with minimal updates)
- [ ] Integration test passes end-to-end (create → execute → approve → complete)
- [ ] Both test files pass `ruff check`

## Verification

- `uv run pytest tests/unit/test_task_execution.py -v` — all 10 pass
- `uv run pytest tests/integration/test_task_execution_integration.py -v` — passes
- `uv run ruff check tests/integration/test_task_execution_integration.py tests/unit/test_task_execution.py` — zero errors

## Inputs

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — T01 output; has `_build_resume_service(session, handlers, user_id)` accepting `user_id` param
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — T01 output; has `_resolve_user_id(submitted_by, db)` and uses `GoogleCalendarProvider` directly
- `packages/connectors/src/helm_connectors/calendar_system.py` — `StubCalendarSystemAdapter` still available (used as test mock replacement)
- `packages/storage/src/helm_storage/models.py` — `UserORM` and `UserCredentialsORM` from S01 (for seeding test user)

## Expected Output

- `tests/integration/test_task_execution_integration.py` — seeds bootstrap user, patches `GoogleCalendarProvider`, removes old credential mocks, passes end-to-end
- `tests/unit/test_task_execution.py` — all 10 tests pass (likely unchanged)

## Observability Impact

T02 is a test-only task; it introduces no new runtime signals but verifies that the signals introduced in T01 are reachable:

- **`calendar_provider_constructed`** (structlog info, fields: `user_id`, `source="db_credentials"`) — emitted by `_build_calendar_provider` in `workflow_runs.py` and by `workflow_status_service.py` during both `execute_task_run` and `execute_after_approval`. The integration test exercises both paths, so this event fires twice per test run (observable via `caplog` or structlog test sinks in future).
- **`calendar_upsert_insert` / `calendar_upsert_success`** — emitted by `GoogleCalendarProvider` during `execute_after_approval`; the integration test patches `helm_providers.google_calendar.build` so the mock `events.insert().execute()` returns `{"id": "test-event-id", "status": "confirmed"}` — these structlog events are emitted from within `GoogleCalendarProvider` and would appear in integration logs.
- **Failure surface**: `RuntimeError("No user found for submitted_by=...")` and `RuntimeError("No Google credentials for user_id=...")` replace the silent stub fallback from the old `_build_calendar_adapter`; the integration test's `_seed_test_user` helper ensures these paths are not triggered.
- **Inspection**: in a failing test run, `session.get(WorkflowRunORM, run_id)` gives the raw ORM status/needs_action at any assertion point without needing external tooling.
