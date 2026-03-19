---
estimated_steps: 5
estimated_files: 2
---

# T02: Rewrite integration tests that use GoogleCalendarAdapter in real-credential blocks

**Slice:** S04 — Replace Calendar Connector in Worker + Bot
**Milestone:** M005

## Description

Two integration test files still construct `GoogleCalendarAdapter(auth)` in their real-credential / mock-transport blocks: `test_weekly_scheduling_end_to_end.py` and `test_weekly_scheduling_with_drift_recovery.py`. Both need to be updated to use `GoogleCalendarProvider(user_id, session)` with seeded `UserORM` + `UserCredentialsORM` rows, following the `_seed_test_user()` pattern established in `test_task_execution_integration.py` (S03).

After T01 deleted `google_calendar.py` from `helm_connectors`, these files would fail at collection time if they still import `GoogleCalendarAdapter`/`GoogleCalendarAuth`. T01 only eliminated references in `apps/` and `tests/unit/`. T02 finishes the job for `tests/integration/`.

Five other integration test files (`test_drift_detection_and_reconciliation.py`, `test_drift_recovery_actions_in_workflow_status.py`, `test_drift_recovery_workflows.py`, `test_workflow_status_routes.py`, `test_task_execution_integration.py`) use only `StubCalendarSystemAdapter` / `StubTaskSystemAdapter` from `helm_connectors` — those imports remain valid (S06 scope). These files need no code changes, but running them confirms the updated `WorkflowStatusService` constructor (with its new stub fallback path) doesn't break anything.

**Relevant installed skill:** None specifically required.

## Steps

1. **Rewrite `tests/integration/test_weekly_scheduling_end_to_end.py`**

   This file has one block (around lines 203-240) that does:
   ```python
   from helm_connectors import GoogleCalendarAdapter, GoogleCalendarAuth
   ...
   auth = GoogleCalendarAuth()
   calendar_system_adapter=GoogleCalendarAdapter(auth),
   ```

   Replace with `GoogleCalendarProvider`. The pattern:

   a. Remove the `GoogleCalendarAdapter, GoogleCalendarAuth` import (line 205 — it's a lazy import inside the test). Keep `StubCalendarSystemAdapter, StubTaskSystemAdapter` from the top-level import (line 22).

   b. Add new imports at the top of the file:
   ```python
   from helm_providers import GoogleCalendarProvider
   from helm_storage.models import UserCredentialsORM, UserORM
   ```

   c. Add a `_seed_test_user(session)` helper (copy the pattern from `test_task_execution_integration.py`):
   ```python
   from datetime import datetime as _real_datetime
   from datetime import timezone as _tz
   
   def _seed_test_user(session):
       user = UserORM(telegram_user_id=12345, display_name="Test User", timezone="UTC")
       session.add(user)
       session.flush()
       far_future = _real_datetime(2099, 12, 31, 23, 59, 59, tzinfo=_tz.utc)
       creds = UserCredentialsORM(
           user_id=user.id,
           provider="google",
           client_id="test-client-id",
           client_secret="test-client-secret",
           access_token="test-access-token",
           refresh_token="test-refresh-token",
           expires_at=far_future,
           email="test@example.com",
       )
       session.add(creds)
       session.flush()
       return user
   ```

   d. In the test function, call `_seed_test_user(session)` early in the test body (after `session` is obtained from the generator). Then replace the `GoogleCalendarAdapter(auth)` block:
   ```python
   # OLD:
   from helm_connectors import GoogleCalendarAdapter, GoogleCalendarAuth
   with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
       ...
       with patch("googleapiclient.discovery.build") as mock_build:
           auth = GoogleCalendarAuth()
           ...calendar_system_adapter=GoogleCalendarAdapter(auth),
   
   # NEW:
   with patch("helm_providers.credentials.Credentials") as mock_creds_class:
       ...
       with patch("helm_providers.google_calendar.build") as mock_build:
           ...calendar_system_adapter=GoogleCalendarProvider(user.id, session),
   ```

   **Critical:** Patch targets must use the importing module's namespace — `helm_providers.google_calendar.build` (not `googleapiclient.discovery.build`) and `helm_providers.credentials.Credentials` (not `google.oauth2.credentials.Credentials`). This is decision D026.

   e. Remove the `monkeypatch.setenv("GOOGLE_CLIENT_ID", ...)` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` lines — the new `GoogleCalendarProvider` reads credentials from `UserCredentialsORM`, not env vars.

2. **Rewrite `tests/integration/test_weekly_scheduling_with_drift_recovery.py`**

   This file has the same pattern repeated in ~4 different blocks (lines ~402, ~491, ~661, ~823) and a top-level import of `GoogleCalendarAdapter, GoogleCalendarAuth` from `helm_connectors` (lines 25-28).

   a. Replace the top-level import block:
   ```python
   # OLD:
   from helm_connectors import (
       GoogleCalendarAdapter,
       GoogleCalendarAuth,
       StubCalendarSystemAdapter,
       StubTaskSystemAdapter,
   )
   
   # NEW:
   from helm_connectors import (
       StubCalendarSystemAdapter,
       StubTaskSystemAdapter,
   )
   from helm_providers import GoogleCalendarProvider
   from helm_storage.models import UserCredentialsORM, UserORM
   ```

   b. Add the same `_seed_test_user(session)` helper.

   c. In each test function, seed the test user and replace all `GoogleCalendarAdapter(auth)` constructions with `GoogleCalendarProvider(user.id, session)`. There are 4 blocks to update. Each follows the same pattern as step 1d.

   d. Update patch targets in each block from `"google.oauth2.credentials.Credentials"` → `"helm_providers.credentials.Credentials"` and `"googleapiclient.discovery.build"` → `"helm_providers.google_calendar.build"`.

   e. Update the file's docstring (line 4) from "Real GoogleCalendarAdapter writes and reads" to "Real GoogleCalendarProvider writes and reads" (or similar).

3. **Run all integration tests**

   ```bash
   uv run pytest tests/integration/test_weekly_scheduling_end_to_end.py \
     tests/integration/test_weekly_scheduling_with_drift_recovery.py \
     tests/integration/test_drift_recovery_actions_in_workflow_status.py \
     tests/integration/test_drift_recovery_workflows.py \
     tests/integration/test_drift_detection_and_reconciliation.py \
     tests/integration/test_workflow_status_routes.py -v
   ```

   All should pass. The stub-only tests confirm the `WorkflowStatusService` constructor's `StubCalendarSystemAdapter` fallback works.

4. **Verify no GoogleCalendarAdapter/Auth references remain in integration tests**

   ```bash
   rg "GoogleCalendarAdapter\|GoogleCalendarAuth" tests/integration/ -t py
   ```
   → 0 results

5. **Run ruff on modified files**

   ```bash
   uv run ruff check tests/integration/test_weekly_scheduling_end_to_end.py \
     tests/integration/test_weekly_scheduling_with_drift_recovery.py --fix
   ```

## Must-Haves

- [ ] `test_weekly_scheduling_end_to_end.py` uses `GoogleCalendarProvider(user.id, session)` — no `GoogleCalendarAdapter`/`GoogleCalendarAuth`
- [ ] `test_weekly_scheduling_with_drift_recovery.py` uses `GoogleCalendarProvider(user.id, session)` in all 4 blocks — no `GoogleCalendarAdapter`/`GoogleCalendarAuth`
- [ ] Patch targets use `helm_providers.google_calendar.build` and `helm_providers.credentials.Credentials` (not original package paths)
- [ ] `_seed_test_user(session)` helper seeds `UserORM` + `UserCredentialsORM` in each file
- [ ] All integration tests pass (including the unchanged stub-only ones)

## Observability Impact

**Signals introduced / changed by this task:**
- Integration tests that use `GoogleCalendarProvider` now emit `calendar_provider_constructed` (info) from `workflow_runs.py` during worker `run()` calls — visible in captured stdout: `source=db_credentials user_id=<id>`.
- `helm_providers.credentials.Credentials` patch scope: when tests mock `helm_providers.credentials.Credentials`, only `build_google_credentials` in that module is intercepted — no effect on other code that imports `google.oauth2.credentials.Credentials` directly.
- `helm_providers.google_calendar.build` patch scope: intercepts only the `build` call in `GoogleCalendarProvider._get_service()` — no global `googleapiclient` interception.

**How a future agent inspects this task:**
- Run `uv run pytest tests/integration/test_weekly_scheduling_end_to_end.py tests/integration/test_weekly_scheduling_with_drift_recovery.py -v` — all 8 tests should pass.
- `rg "GoogleCalendarAdapter|GoogleCalendarAuth" tests/integration/ -t py` → 0 results confirms clean migration.
- Captured stdout during passing tests shows `calendar_provider_constructed source=db_credentials` — confirms `GoogleCalendarProvider` used real DB path (seeded credentials), not env-var path.

**Failure visibility:**
- If `TELEGRAM_ALLOWED_USER_ID` env var is unset, worker `run()` raises `RuntimeError("Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set")` — immediately visible in test failure output.
- If `_seed_test_user()` is called but `UserCredentialsORM` row is missing, `GoogleCalendarProvider` raises `RuntimeError("No credentials found...")` at `execute_pending_sync_step` time.
- If `past_event_guard` fires (time freeze missing), the workflow reaches `blocked_validation` instead of `awaiting_approval` — assertion `data["paused_state"] == "awaiting_approval"` will fail with `'blocked_validation' == 'awaiting_approval'`.

## Verification

- `uv run pytest tests/integration/test_weekly_scheduling_end_to_end.py tests/integration/test_weekly_scheduling_with_drift_recovery.py -v` → all pass
- `uv run pytest tests/integration/test_drift_recovery_actions_in_workflow_status.py tests/integration/test_drift_recovery_workflows.py tests/integration/test_drift_detection_and_reconciliation.py tests/integration/test_workflow_status_routes.py -v` → all pass (confirms stub fallback works)
- `rg "GoogleCalendarAdapter\|GoogleCalendarAuth" tests/integration/ -t py` → 0 results
- `uv run ruff check tests/integration/test_weekly_scheduling_end_to_end.py tests/integration/test_weekly_scheduling_with_drift_recovery.py` → 0 errors

## Inputs

- `tests/integration/test_weekly_scheduling_end_to_end.py` — 420 lines; 1 real-credential block using `GoogleCalendarAdapter`
- `tests/integration/test_weekly_scheduling_with_drift_recovery.py` — 1077 lines; 4 real-credential blocks using `GoogleCalendarAdapter`
- `tests/integration/test_task_execution_integration.py` — reference for `_seed_test_user()` pattern (lines 107-131); `UserORM` + `UserCredentialsORM` with `expires_at=far_future` to skip token refresh
- T01 output: `packages/connectors/google_calendar.py` deleted; `GoogleCalendarAdapter`/`GoogleCalendarAuth` no longer importable from `helm_connectors`
- D026 (decision): patch targets must use the importing module's namespace — `helm_providers.google_calendar.build` and `helm_providers.credentials.Credentials`
- S02 Forward Intelligence: `_service` injection pattern is fully established; instantiate `GoogleCalendarProvider(user_id, db)` directly — constructor handles credential lookup internally
- `OPERATOR_TIMEZONE` env var must be set for any import of `helm_worker.jobs.workflow_runs` (worker config reads it at import time)

## Expected Output

- `tests/integration/test_weekly_scheduling_end_to_end.py` — updated to use `GoogleCalendarProvider`; passes
- `tests/integration/test_weekly_scheduling_with_drift_recovery.py` — updated in all 4 blocks; passes
- All other integration tests pass unchanged (confirms no regression from T01's `WorkflowStatusService` constructor change)
