---
estimated_steps: 7
estimated_files: 6
---

# T01: Scaffold packages/providers + credential helper + Protocol definitions

**Slice:** S02 — google_workspace_mcp Integration + Provider Protocols
**Milestone:** M005

## Description

Create the `packages/providers/` package structure, add `google-workspace-mcp` as a dev dependency, register the package path in `pyproject.toml`, and implement the two foundational modules: `credentials.py` (shared credential-build + token-refresh + DB write-back) and `protocols.py` (`CalendarProvider` and `InboxProvider` structural typing Protocols). Also create a `factory.py` skeleton and the package `__init__.py`.

This is the foundation task — nothing in S02 can import `helm_providers` until this is done.

**Relevant installed skills:** None needed (pure Python package scaffolding + typing).

## Steps

1. **Add `google-workspace-mcp` to `pyproject.toml` dev dependencies.** Open `pyproject.toml` and add `"google-workspace-mcp>=2.0.0"` to the `[project.optional-dependencies].dev` list (alphabetical order). Also add `"pytz>=2024.1"` if not present — `google_workspace_mcp.services.calendar` imports `pytz`.

2. **Register `packages/providers/src` in setuptools find config.** In `pyproject.toml` under `[tool.setuptools.packages.find]`, add `"packages/providers/src"` to the `where` list. Add `"helm_providers"` and `"helm_providers.*"` to the `include` list.

3. **Create package directory and `__init__.py`.** Create `packages/providers/src/helm_providers/__init__.py` with placeholder exports for the public symbols that will be filled in by T02/T03. For now, export `CalendarProvider`, `InboxProvider` from `.protocols`, and `build_google_credentials` from `.credentials`.

4. **Create `credentials.py`.** Implement `build_google_credentials(creds: UserCredentialsORM, db: Session) -> google.oauth2.credentials.Credentials`:
   - Import `google.oauth2.credentials.Credentials` and `google.auth.transport.requests.Request`
   - Build a `Credentials` object from `creds.access_token`, `creds.refresh_token`, `creds.client_id`, `creds.client_secret`, with `token_uri="https://oauth2.googleapis.com/token"`
   - Handle the bootstrap case: if `creds.access_token is None`, the token needs refreshing
   - Check `google_creds.valid` — if not valid (expired or no token), call `google_creds.refresh(Request())`
   - On successful refresh, write back `creds.access_token = google_creds.token` and `creds.expires_at = google_creds.expiry.replace(tzinfo=UTC) if google_creds.expiry else None`; then `db.commit()`
   - Log `google_credentials_refreshed` (info, fields: user_id placeholder) on refresh; `google_credentials_refresh_failed` (error) on exception
   - **CRITICAL:** Never log `access_token`, `refresh_token`, or `client_secret`
   - Accept `user_id: int` as a parameter (for logging only) alongside `creds` and `db`

5. **Create `protocols.py`.** Define two Protocol classes using `typing.Protocol` (structural typing, no ABC):

   ```python
   from typing import Protocol
   from zoneinfo import ZoneInfo
   from helm_orchestration.schemas import (
       CalendarSyncRequest, CalendarSyncResult,
       SyncLookupRequest, SyncLookupResult,
   )

   class CalendarProvider(Protocol):
       def upsert_calendar_block(self, request: CalendarSyncRequest) -> CalendarSyncResult: ...
       def reconcile_calendar_block(self, request: SyncLookupRequest) -> SyncLookupResult: ...
       def list_today_events(self, calendar_id: str, timezone: ZoneInfo) -> list[dict]: ...

   class InboxProvider(Protocol):
       def pull_new_messages_report(self, manual_payload: list[dict] | None = None) -> "PullMessagesReport": ...
       def pull_changed_messages_report(self, *, last_history_cursor: str | None, manual_payload: list[dict] | None = None) -> "PullMessagesReport": ...
       def send_reply(self, *, provider_thread_id: str, to_address: str, subject: str, body_text: str) -> "GmailSendResult": ...
   ```

   Use `from __future__ import annotations` to handle forward references for `PullMessagesReport` and `GmailSendResult` (defined in `gmail.py`, not yet created). Alternatively, use string annotations.

6. **Create `factory.py` skeleton.** Write a `ProviderFactory` class with `__init__(self, user_id: int, db: Session)` that stores the args. Add `calendar(self) -> CalendarProvider` and `inbox(self) -> InboxProvider` method stubs that raise `NotImplementedError("Completed in T02/T03")`. These will be filled in by T02 and T03.

7. **Run `uv sync` and verify imports.** Execute `uv sync` to install `google-workspace-mcp` and its transitive deps. Then run import smoke tests.

## Must-Haves

- [ ] `google-workspace-mcp>=2.0.0` in `pyproject.toml` `[project.optional-dependencies].dev`
- [ ] `packages/providers/src` in `[tool.setuptools.packages.find].where`
- [ ] `helm_providers` and `helm_providers.*` in `[tool.setuptools.packages.find].include`
- [ ] `build_google_credentials(user_id, creds, db)` handles `access_token=None` bootstrap case
- [ ] Token refresh writes back `access_token` and `expires_at` to ORM + commits
- [ ] `CalendarProvider` Protocol has `upsert_calendar_block`, `reconcile_calendar_block`, `list_today_events`
- [ ] `InboxProvider` Protocol has `pull_new_messages_report`, `pull_changed_messages_report`, `send_reply`
- [ ] No secrets logged in `credentials.py`
- [ ] `gauth.get_credentials()` is NOT imported or called anywhere

## Verification

- `uv run python -c "from helm_providers.protocols import CalendarProvider, InboxProvider; print('ok')"` — succeeds
- `uv run python -c "from helm_providers.credentials import build_google_credentials; print('ok')"` — succeeds
- `uv run python -c "import google_workspace_mcp; print(google_workspace_mcp.__version__)"` — prints version
- `ruff check packages/providers/src/` — 0 errors

## Inputs

- `pyproject.toml` — current dev dependencies list and setuptools config
- `packages/storage/src/helm_storage/models.py` — `UserCredentialsORM` shape: `access_token: str | None`, `refresh_token: str`, `client_id: str | None`, `client_secret: str | None`, `expires_at: datetime | None`, `email: str`
- `packages/storage/src/helm_storage/repositories/users.py` — `get_credentials(user_id, provider, db) -> UserCredentialsORM | None`
- `packages/orchestration/src/helm_orchestration/schemas.py` — `CalendarSyncRequest`, `CalendarSyncResult`, `SyncLookupRequest`, `SyncLookupResult` types
- S01 summary: `access_token` and `expires_at` are nullable on bootstrap; credential refresh must handle `token=None`

## Expected Output

- `pyproject.toml` — updated with `google-workspace-mcp` dep and `packages/providers/src` path
- `packages/providers/src/helm_providers/__init__.py` — package init with protocol + credential exports
- `packages/providers/src/helm_providers/credentials.py` — `build_google_credentials(user_id, creds, db)` with refresh + write-back
- `packages/providers/src/helm_providers/protocols.py` — `CalendarProvider` and `InboxProvider` Protocol classes
- `packages/providers/src/helm_providers/factory.py` — skeleton `ProviderFactory` class

## Observability Impact

**New signals introduced:**
- `google_credentials_refreshed` (structlog, level=info): emitted in `credentials.py` whenever a stale or missing `access_token` is refreshed. Fields: `user_id` (int), `expires_at` (ISO string or None). Confirms token refresh write-back succeeded.
- `google_credentials_refresh_failed` (structlog, level=error): emitted on any exception during `google_creds.refresh(Request())`. Fields: `user_id` (int), `error` (exception class name). Confirms the credential bootstrap failure is visible.

**Inspection surfaces:**
- `SELECT access_token IS NOT NULL, expires_at FROM user_credentials WHERE provider='google'` — after any `build_google_credentials` call, the row should have a non-null `access_token` and a populated `expires_at` (or still null if refresh also returned no expiry).

**Failure visibility:**
- If `access_token` is None and refresh raises, the `google_credentials_refresh_failed` log event surfaces the exact exception class; calling code will see the exception propagate.
- `user_id` and `expires_at` are the only credential-related fields that appear in log events — `access_token`, `refresh_token`, and `client_secret` are never logged.

**No runtime services or DB schema changes in this task** — the package is scaffolding only; no new ORM tables or migrations are introduced.
