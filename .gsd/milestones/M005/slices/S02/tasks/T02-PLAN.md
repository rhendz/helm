---
estimated_steps: 6
estimated_files: 5
---

# T02: GoogleCalendarProvider + ProviderFactory + calendar unit tests

**Slice:** S02 — google_workspace_mcp Integration + Provider Protocols
**Milestone:** M005

## Description

Implement `GoogleCalendarProvider` satisfying the `CalendarProvider` Protocol. This is the core risk-retirement task for S02: it proves the `gauth` bypass pattern by constructing a `CalendarService` with `_service` injected directly, bypassing `gauth.get_credentials()` entirely. Complete the `ProviderFactory.calendar()` method. Write unit tests covering credentials, the calendar provider, and the factory — all using mocked API clients (no real Google credentials).

The calendar provider ports logic verbatim from `packages/connectors/src/helm_connectors/google_calendar.py` (the `GoogleCalendarAdapter` class). The key methods are `upsert_calendar_block`, `reconcile_calendar_block`, `list_today_events`, and `_fingerprint_event`.

**Relevant installed skills:** `test` skill for test generation patterns.

## Steps

1. **Create `packages/providers/src/helm_providers/google_calendar.py`.** Implement `GoogleCalendarProvider`:

   ```python
   class GoogleCalendarProvider:
       def __init__(self, user_id: int, db: Session) -> None:
   ```

   In `__init__`:
   - Call `get_credentials(user_id, "google", db)` from `helm_storage.repositories.users`
   - If `None`, raise `RuntimeError(f"No Google credentials for user_id={user_id}")`
   - Call `build_google_credentials(user_id, creds, db)` from `helm_providers.credentials`
   - Construct `CalendarService` bypassing `__init__`:
     ```python
     from google_workspace_mcp.services.calendar import CalendarService
     from googleapiclient.discovery import build
     svc = CalendarService.__new__(CalendarService)
     svc.service_name = "calendar"
     svc.version = "v3"
     svc._service = build("calendar", "v3", credentials=google_creds)
     self._cal_svc = svc
     ```
   - **CRITICAL:** Do NOT call `CalendarService()` — that triggers `BaseGoogleService.__init__` which is fine (it doesn't call `gauth`), but `__new__` + manual setup is the pattern the research validated. Either approach works; the key constraint is that `_service` must be set BEFORE `svc.service` property is accessed.
   - Store `self._user_id = user_id` for logging

2. **Port `upsert_calendar_block` from `GoogleCalendarAdapter`.** Copy the full method body from `packages/connectors/src/helm_connectors/google_calendar.py`. Key differences from the connector version:
   - Use `self._cal_svc.service` instead of `self._get_service()` to get the API client
   - Same `CalendarSyncRequest` → Google API → `CalendarSyncResult` flow
   - Same HTTP error classification (404=terminal, 429=retryable, 5xx=retryable)
   - Import `CalendarSyncResult`, `SyncOutcomeStatus`, `SyncRetryDisposition` from `helm_orchestration.schemas`

3. **Port `reconcile_calendar_block` and `list_today_events`.** Same approach — copy from the connector, replace `self._get_service()` with `self._cal_svc.service`. Port `_fingerprint_event` as a private method.

4. **Complete `ProviderFactory`.** Update `packages/providers/src/helm_providers/factory.py`:
   ```python
   from helm_providers.google_calendar import GoogleCalendarProvider

   class ProviderFactory:
       def __init__(self, user_id: int, db: Session) -> None:
           self._user_id = user_id
           self._db = db

       def calendar(self) -> "CalendarProvider":
           return GoogleCalendarProvider(self._user_id, self._db)
   ```
   Leave `inbox()` raising `NotImplementedError` — completed in T03.

5. **Update `__init__.py` exports.** Add `GoogleCalendarProvider` and `ProviderFactory` to `packages/providers/src/helm_providers/__init__.py` exports.

6. **Write unit tests in `tests/unit/test_google_providers.py`.** Create the test file with these test cases:

   **Credential tests:**
   - `test_build_google_credentials_refreshes_when_access_token_none` — mock `google.oauth2.credentials.Credentials` and `Request`; verify refresh called when `access_token=None`; verify write-back of `access_token` and `expires_at` to ORM + `db.commit()`
   - `test_build_google_credentials_skips_refresh_when_valid` — set `access_token` and `expires_at` in future; verify refresh NOT called; verify no DB commit
   - `test_build_google_credentials_refresh_failure_raises` — mock refresh to raise; verify exception propagates

   **Calendar provider tests:**
   - `test_calendar_provider_raises_on_missing_credentials` — mock `get_credentials` returning `None`; verify `RuntimeError`
   - `test_upsert_calendar_block_insert` — mock the `events().insert().execute()` chain on the service; verify `CalendarSyncResult` with `SUCCEEDED` status and `external_object_id` set
   - `test_upsert_calendar_block_update` — same pattern with `external_object_id` in payload; verify `events().update()` called
   - `test_reconcile_calendar_block_found` — mock `events().get().execute()` returning event dict; verify `SyncLookupResult.found=True`
   - `test_reconcile_calendar_block_not_found_404` — mock `events().get()` raising `HttpError` with 404; verify `found=False`
   - `test_list_today_events` — mock `events().list().execute()` returning items; verify list returned

   **Factory test:**
   - `test_provider_factory_calendar` — verify `ProviderFactory(user_id, db).calendar()` returns a `GoogleCalendarProvider`

   **Test fixtures:**
   - Use SQLite in-memory DB with `Base.metadata.create_all()` (same pattern as S01 tests)
   - Seed a `UserORM` and `UserCredentialsORM` row in the fixture
   - Mock `googleapiclient.discovery.build` to avoid real API calls
   - Mock `google.oauth2.credentials.Credentials` to avoid real token refresh
   - Use `unittest.mock.patch` / `MagicMock` — no need for `pytest-mock` (not installed)

## Must-Haves

- [ ] `GoogleCalendarProvider.__init__` raises `RuntimeError` when `get_credentials` returns `None`
- [ ] `CalendarService.__new__` pattern used — `_service` set before any `svc.service` access
- [ ] `upsert_calendar_block` handles insert (no `external_object_id`) and update (with `external_object_id`)
- [ ] `reconcile_calendar_block` handles found, not-found (404), and cancelled events
- [ ] `list_today_events` computes correct day boundaries in operator timezone
- [ ] `_fingerprint_event` normalizes datetimes to UTC for deterministic comparison
- [ ] `ProviderFactory.calendar()` returns a working `GoogleCalendarProvider`
- [ ] Unit tests pass with `uv run pytest tests/unit/test_google_providers.py -v`
- [ ] `gauth.get_credentials()` is NOT imported or called anywhere in new code

## Verification

- `uv run pytest tests/unit/test_google_providers.py -v -k "calendar or factory or credential"` — all pass
- `uv run python -c "from helm_providers import GoogleCalendarProvider, ProviderFactory; print('ok')"` — succeeds
- `ruff check packages/providers/src/helm_providers/google_calendar.py tests/unit/test_google_providers.py` — 0 errors

## Observability Impact

- Signals added: structlog events `calendar_upsert_success`, `calendar_upsert_failed`, `reconcile_calendar_block_success`, `reconcile_calendar_block_failed`, `list_today_events`, `list_today_events_complete` — all ported from existing connector with same event names
- How a future agent inspects this: `uv run pytest tests/unit/test_google_providers.py -v` shows per-test pass/fail
- Failure state exposed: `RuntimeError` with clear message on missing credentials; `CalendarSyncResult.error_summary` on API failures

## Inputs

- `packages/providers/src/helm_providers/credentials.py` — `build_google_credentials(user_id, creds, db)` from T01
- `packages/providers/src/helm_providers/protocols.py` — `CalendarProvider` Protocol from T01
- `packages/providers/src/helm_providers/factory.py` — skeleton from T01
- `packages/connectors/src/helm_connectors/google_calendar.py` — source for `upsert_calendar_block`, `reconcile_calendar_block`, `list_today_events`, `_fingerprint_event` logic. Port these method bodies into the new provider.
- `packages/orchestration/src/helm_orchestration/schemas.py` — `CalendarSyncRequest`, `CalendarSyncResult`, `SyncOutcomeStatus`, `SyncRetryDisposition`, `SyncLookupRequest`, `SyncLookupResult`
- `packages/storage/src/helm_storage/models.py` — `UserORM`, `UserCredentialsORM` for test fixtures
- `packages/storage/src/helm_storage/repositories/users.py` — `get_credentials(user_id, provider, db)`

## Expected Output

- `packages/providers/src/helm_providers/google_calendar.py` — full `GoogleCalendarProvider` implementation
- `packages/providers/src/helm_providers/factory.py` — completed `ProviderFactory.calendar()` method
- `packages/providers/src/helm_providers/__init__.py` — updated exports
- `tests/unit/test_google_providers.py` — ~10 unit tests covering credentials, calendar provider, factory
