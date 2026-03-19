# S02: google_workspace_mcp Integration + Provider Protocols

**Goal:** `GoogleCalendarProvider` and `GmailProvider` exist in `packages/providers/`, satisfy `CalendarProvider` and `InboxProvider` Protocol classes, and perform real credential-aware API calls via `google_workspace_mcp` services with the `gauth` bypass pattern.

**Demo:** `from helm_providers import GoogleCalendarProvider, GmailProvider, ProviderFactory, CalendarProvider, InboxProvider` succeeds; unit tests prove both providers satisfy their protocols with mocked API clients; credential refresh writes back `access_token` and `expires_at` to `UserCredentialsORM`.

## Must-Haves

- `google-workspace-mcp` added to `pyproject.toml` `[project.optional-dependencies].dev`
- `packages/providers/src` added to `[tool.setuptools.packages.find].where`
- `CalendarProvider` Protocol with `upsert_calendar_block`, `reconcile_calendar_block`, `list_today_events` methods
- `InboxProvider` Protocol with `pull_new_messages_report`, `pull_changed_messages_report`, `send_reply` methods
- `_build_google_credentials(creds, db)` shared helper: builds `google.oauth2.credentials.Credentials`, refreshes if needed, writes back `access_token` + `expires_at` to DB
- `GoogleCalendarProvider(user_id, db)` satisfying `CalendarProvider` — ports logic from `helm_connectors.google_calendar`
- `GmailProvider(user_id, db)` satisfying `InboxProvider` — ports logic from `helm_connectors.gmail`
- `ProviderFactory(user_id, db)` returning typed providers
- `NormalizedGmailMessage`, `PullMessagesReport`, `GmailSendResult`, `GmailSendError` re-exported from `helm_providers.gmail`
- Unit tests proving both providers work with mocked API clients (no real credentials required)
- `gauth.get_credentials()` is NEVER called — all credential paths bypass it via `_service` injection

## Proof Level

- This slice proves: contract + integration (credential injection pattern)
- Real runtime required: no (unit tests use mocked API clients; real-credential smoke is optional E2E)
- Human/UAT required: no

## Verification

- `uv run pytest tests/unit/test_google_providers.py -v` — all tests pass
- `uv run python -c "from helm_providers import GoogleCalendarProvider, GmailProvider, ProviderFactory, CalendarProvider, InboxProvider; print('ok')"` — import smoke
- `uv run python -c "from helm_providers.gmail import NormalizedGmailMessage, PullMessagesReport, GmailSendResult, GmailSendError; print('ok')"` — Gmail type re-exports
- `uv run python -c "from helm_providers.protocols import CalendarProvider, InboxProvider; print('ok')"` — protocol imports
- `uv run python -c "from helm_providers.credentials import build_google_credentials; print('ok')"` — credential helper import
- `ruff check packages/providers/src/ tests/unit/test_google_providers.py` — 0 errors

## Observability / Diagnostics

- Runtime signals: structlog events `google_credentials_refreshed` (level=info, fields: user_id, expires_at), `google_credentials_refresh_failed` (level=error, fields: user_id, error), `calendar_upsert_success` / `calendar_upsert_failed`, `gmail_pull_completed`, `gmail_send_completed` / `gmail_send_failed`
- Inspection surfaces: `SELECT access_token IS NOT NULL, expires_at FROM user_credentials WHERE provider='google'` — confirms token refresh write-back
- Failure visibility: structlog error events with user_id, operation name, and error class; `GoogleCalendarProvider` and `GmailProvider` raise `RuntimeError` on missing credentials (not `AttributeError`)
- Redaction constraints: `access_token`, `refresh_token`, `client_secret` NEVER logged; only `user_id` and `expires_at` appear in log events

## Integration Closure

- Upstream surfaces consumed: `get_credentials(user_id, "google", db)` from `packages/storage/src/helm_storage/repositories/users.py` (S01); `UserCredentialsORM` from `packages/storage/src/helm_storage/models.py` (S01); `CalendarSyncRequest`, `CalendarSyncResult`, `SyncLookupRequest`, `SyncLookupResult` from `packages/orchestration/src/helm_orchestration/schemas.py`
- New wiring introduced in this slice: `packages/providers/` package with `helm_providers` importable namespace; no runtime hookup (S04/S05 wire providers into worker/bot)
- What remains before the milestone is truly usable end-to-end: S03 (unified `/task` pipeline), S04 (calendar connector replacement in worker/bot), S05 (Gmail connector replacement), S06 (delete `packages/connectors/`)

## Tasks

- [x] **T01: Scaffold packages/providers + credential helper + Protocol definitions** `est:30m`
  - Why: Nothing can import `helm_providers` until the package exists, the dependency is declared, and `pyproject.toml` knows about `packages/providers/src`. Credentials and protocols are foundational — T02 and T03 both depend on them.
  - Files: `pyproject.toml`, `packages/providers/src/helm_providers/__init__.py`, `packages/providers/src/helm_providers/credentials.py`, `packages/providers/src/helm_providers/protocols.py`, `packages/providers/src/helm_providers/factory.py`
  - Do: Add `google-workspace-mcp>=2.0.0` to dev deps in `pyproject.toml`. Add `packages/providers/src` to `[tool.setuptools.packages.find].where` and `helm_providers` to include list. Create `credentials.py` with `build_google_credentials(creds, db)` — builds `Credentials` from `UserCredentialsORM`, handles `access_token=None` bootstrap case, refreshes via `google.auth.transport.requests.Request()`, writes back `access_token` + `expires_at`. Create `protocols.py` with `CalendarProvider` and `InboxProvider` Protocol classes. Create `factory.py` skeleton (will be completed in T02). Create `__init__.py` exporting protocols. Run `uv sync` to install new dep.
  - Verify: `uv run python -c "from helm_providers.protocols import CalendarProvider, InboxProvider; from helm_providers.credentials import build_google_credentials; print('ok')"` succeeds
  - Done when: `packages/providers/src/helm_providers/` exists with `credentials.py`, `protocols.py`, `factory.py` skeleton, `__init__.py`; `google-workspace-mcp` is importable; all import smoke tests pass

- [x] **T02: GoogleCalendarProvider + ProviderFactory + calendar unit tests** `est:45m`
  - Why: This is the core risk-retirement task. The calendar provider proves the `gauth` bypass pattern (inject `_service` directly into `CalendarService`), and the unit tests confirm the provider satisfies `CalendarProvider` protocol with mocked API clients. Factory wiring is trivially testable alongside the provider.
  - Files: `packages/providers/src/helm_providers/google_calendar.py`, `packages/providers/src/helm_providers/factory.py`, `packages/providers/src/helm_providers/__init__.py`, `tests/unit/test_google_providers.py`
  - Do: Create `GoogleCalendarProvider(user_id, db)` — calls `get_credentials(user_id, "google", db)`, builds google creds via `build_google_credentials()`, constructs `CalendarService` with `_service` injected via `CalendarService.__new__()` + manual attribute set. Port `upsert_calendar_block`, `reconcile_calendar_block`, `list_today_events`, `_fingerprint_event` from `helm_connectors.google_calendar`. Complete `ProviderFactory`. Write unit tests covering: credential lookup failure raises RuntimeError, credential refresh + write-back, `upsert_calendar_block` insert + update, `reconcile_calendar_block` found + not-found + cancelled, `list_today_events` returns events, `ProviderFactory.calendar()` returns provider. Update `__init__.py` exports.
  - Verify: `uv run pytest tests/unit/test_google_providers.py -v -k "calendar or factory or credential"` — all pass; `ruff check packages/providers/src/ tests/unit/test_google_providers.py` — 0 errors
  - Done when: `GoogleCalendarProvider` satisfies `CalendarProvider` protocol in unit tests; `ProviderFactory.calendar()` returns a working `GoogleCalendarProvider`; credential refresh writes back to DB in test

- [x] **T03: GmailProvider + Gmail unit tests + final exports verification** `est:50m`
  - Why: Ports all Gmail connector logic (history polling, message normalization, send) into `GmailProvider` satisfying `InboxProvider` protocol. Also finalizes all `__init__.py` exports and runs the complete verification sweep.
  - Files: `packages/providers/src/helm_providers/gmail.py`, `packages/providers/src/helm_providers/__init__.py`, `tests/unit/test_google_providers.py`
  - Do: Create `GmailProvider(user_id, db)` — same credential + `_service` injection pattern as calendar. Transplant all private helper functions from `helm_connectors.gmail`: `_list_changed_message_ids`, `_list_recent_message_ids`, `_normalize_message_ids`, `_build_gmail_raw_payload`, `_extract_headers`, `_extract_body_text`, `_decode_base64url`, `normalize_message`, `normalize_message_checked`, `_get_current_history_cursor`, `_history_recovery_reason`, `_http_status`, `_raise_send_error`. Implement `pull_new_messages_report`, `pull_changed_messages_report` (preserve bootstrap fallback when `last_history_cursor=None`), `send_reply` (adapt `to_address: str` → internal API call). Re-export `NormalizedGmailMessage`, `PullMessagesReport`, `GmailSendResult`, `GmailSendError` from `helm_providers.gmail` — define them in this file (transplant from `helm_connectors.gmail`). Add Gmail unit tests: `pull_new_messages_report` with mocked service, `pull_changed_messages_report` with + without history cursor, `send_reply` success + error cases, `GmailSendError` attributes. Update `__init__.py` to export all public symbols. Run full verification suite.
  - Verify: `uv run pytest tests/unit/test_google_providers.py -v` — all tests pass; all six import smoke commands from slice verification pass; `ruff check packages/providers/src/ tests/unit/test_google_providers.py` — 0 errors
  - Done when: `GmailProvider` satisfies `InboxProvider` protocol in unit tests; `NormalizedGmailMessage`, `PullMessagesReport`, `GmailSendResult`, `GmailSendError` importable from `helm_providers.gmail`; all slice-level verification checks pass

## Files Likely Touched

- `pyproject.toml`
- `packages/providers/src/helm_providers/__init__.py`
- `packages/providers/src/helm_providers/credentials.py`
- `packages/providers/src/helm_providers/protocols.py`
- `packages/providers/src/helm_providers/google_calendar.py`
- `packages/providers/src/helm_providers/gmail.py`
- `packages/providers/src/helm_providers/factory.py`
- `tests/unit/test_google_providers.py`
