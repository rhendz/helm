---
estimated_steps: 7
estimated_files: 4
---

# T03: GmailProvider + Gmail unit tests + final exports verification

**Slice:** S02 — google_workspace_mcp Integration + Provider Protocols
**Milestone:** M005

## Description

Implement `GmailProvider` satisfying the `InboxProvider` Protocol. This task ports all Gmail connector logic from `packages/connectors/src/helm_connectors/gmail.py` — including the data classes (`NormalizedGmailMessage`, `PullMessagesReport`, `GmailSendResult`, `GmailSendError`), message normalization functions, history-cursor polling, and send_reply. Also completes `ProviderFactory.inbox()`, finalizes all `__init__.py` exports, and runs the full slice verification sweep.

The Gmail provider is the largest single module in S02. The key difference from the calendar provider is that Gmail history polling (`history().list()`) has no MCP equivalent, so we access the raw `googleapiclient.discovery.Resource` directly via the injected `_service`.

**Relevant installed skills:** `test` skill for test generation patterns.

## Steps

1. **Create `packages/providers/src/helm_providers/gmail.py`.** Start by transplanting the data classes from `packages/connectors/src/helm_connectors/gmail.py`:
   - `NormalizedGmailMessage` — frozen dataclass with `provider_message_id`, `provider_thread_id`, `from_address`, `subject`, `body_text`, `received_at`, `normalized_at`, `source`
   - `PullMessagesReport` — frozen dataclass with `messages`, `failure_counts`, `next_history_cursor`, `mode`, `recovery_reason`
   - `GmailSendResult` — frozen dataclass with `provider_message_id`, `provider_thread_id`, `from_address`, `to_address`, `subject`, `body_text`, `sent_at`, `source`
   - `GmailSendError` — Exception subclass with `failure_class`, `provider_error_code`
   - `NORMALIZATION_ERROR_MISSING_ID` and `NORMALIZATION_ERROR_INVALID_PAYLOAD` constants

   Copy these EXACTLY — field names, types, defaults must match so downstream code (S05) can switch import paths without changes.

2. **Transplant normalization + helper functions.** Copy verbatim from the connector:
   - `_parse_received_at(value, *, fallback)` — timestamp parsing
   - `normalize_message(raw_payload, *, normalized_at)` — raw dict → `NormalizedGmailMessage`
   - `normalize_message_checked(raw_payload, *, normalized_at)` — safe version returning tuple
   - `_decode_base64url(value)` — base64 decoding
   - `_extract_headers(payload)` — header dict extraction
   - `_extract_body_text(payload)` — body text from MIME parts
   - `_http_status(exc)` — extract HTTP status from exceptions
   - `_raise_send_error(exc)` — classify and raise `GmailSendError`

3. **Implement `GmailProvider` class.** Constructor pattern:
   ```python
   class GmailProvider:
       def __init__(self, user_id: int, db: Session) -> None:
           creds = get_credentials(user_id, "google", db)
           if creds is None:
               raise RuntimeError(f"No Google credentials for user_id={user_id}")
           google_creds = build_google_credentials(user_id, creds, db)
           # Bypass gauth: inject _service directly into GmailService
           from google_workspace_mcp.services.gmail import GmailService
           from googleapiclient.discovery import build
           svc = GmailService.__new__(GmailService)
           svc.service_name = "gmail"
           svc.version = "v1"
           svc._service = build("gmail", "v1", credentials=google_creds)
           self._gmail_svc = svc
           self._user_id = user_id
           self._sender_email = creds.email
   ```

   Note: The connector reads `GMAIL_USER_EMAIL` from env; the provider reads `creds.email` from `UserCredentialsORM` instead (multi-user ready).

4. **Implement the three `InboxProvider` methods on `GmailProvider`:**

   **`pull_new_messages_report(self, manual_payload=None)`:**
   - If `manual_payload` is not None, delegate to `_normalize_manual_payload(manual_payload, ...)`
   - Otherwise, use `self._gmail_svc.service` (the raw API resource) to call `users().messages().list(userId="me", maxResults=25, includeSpamTrash=False)`
   - For each message ID, call `_build_gmail_raw_payload(service, message_id)` then normalize
   - Get current history cursor via `_get_current_history_cursor(service)`
   - Return `PullMessagesReport`

   **`pull_changed_messages_report(self, *, last_history_cursor, manual_payload=None)`:**
   - If `manual_payload` is not None, delegate to `_normalize_manual_payload`
   - If `last_history_cursor is None`, fall back to `pull_new_messages_report()` (bootstrap case — MUST preserve this)
   - Otherwise, call `_list_changed_message_ids(service, start_history_cursor=last_history_cursor)`
   - On exception, detect recovery reason via `_history_recovery_reason(exc)`, fall back to `pull_new_messages_report()`
   - Update `next_history_cursor` via `_get_current_history_cursor` if no change detected

   **`send_reply(self, *, provider_thread_id, to_address, subject, body_text)`:**
   - Validate `to_address` and `body_text` — raise `GmailSendError` if empty
   - Build MIME message using `email.message.EmailMessage`, set headers, base64-encode
   - Send via `self._gmail_svc.service.users().messages().send(userId="me", body=payload)`
   - Return `GmailSendResult` with `from_address=self._sender_email`
   - On error, delegate to `_raise_send_error(exc)` for proper classification

   **Private methods:** Transplant as methods on the class or as module-level functions (module-level preferred for consistency with the connector):
   - `_list_changed_message_ids(service, *, start_history_cursor)` → returns `(list[str], str | None)`
   - `_list_recent_message_ids(service)` → returns `list[str]`
   - `_normalize_message_ids(service, *, message_ids, logger, next_history_cursor, mode)` → `PullMessagesReport`
   - `_build_gmail_raw_payload(service, message_id)` → `dict`
   - `_normalize_manual_payload(manual_payload, *, logger, next_history_cursor, mode)` → `PullMessagesReport`
   - `_get_current_history_cursor(service)` → `str | None`

5. **Complete `ProviderFactory.inbox()`.** Update `factory.py`:
   ```python
   from helm_providers.gmail import GmailProvider

   def inbox(self) -> "InboxProvider":
       return GmailProvider(self._user_id, self._db)
   ```

6. **Finalize `__init__.py` exports.** Update `packages/providers/src/helm_providers/__init__.py` to export ALL public symbols:
   ```python
   from helm_providers.protocols import CalendarProvider, InboxProvider
   from helm_providers.credentials import build_google_credentials
   from helm_providers.google_calendar import GoogleCalendarProvider
   from helm_providers.gmail import (
       GmailProvider,
       NormalizedGmailMessage,
       PullMessagesReport,
       GmailSendResult,
       GmailSendError,
   )
   from helm_providers.factory import ProviderFactory
   ```

7. **Add Gmail unit tests to `tests/unit/test_google_providers.py`.** Append these test cases to the existing file:

   - `test_gmail_provider_raises_on_missing_credentials` — mock `get_credentials` returning `None`; verify `RuntimeError`
   - `test_pull_new_messages_report_manual_payload` — pass a list of raw dicts; verify `PullMessagesReport` with correct `NormalizedGmailMessage` entries
   - `test_pull_new_messages_report_from_api` — mock the Gmail API service chain (`users().messages().list().execute()` + `users().messages().get().execute()`); verify messages normalized
   - `test_pull_changed_messages_report_bootstrap_fallback` — call with `last_history_cursor=None`; verify it falls back to `pull_new_messages_report` behavior and `mode="bootstrap"`
   - `test_pull_changed_messages_report_with_cursor` — mock `history().list().execute()` returning message IDs; verify history mode
   - `test_send_reply_success` — mock `users().messages().send().execute()` returning `{"id": "msg123", "threadId": "t456"}`; verify `GmailSendResult`
   - `test_send_reply_empty_recipient_raises` — verify `GmailSendError` with `failure_class="invalid_recipient"`
   - `test_send_reply_empty_body_raises` — verify `GmailSendError` with `failure_class="invalid_payload"`
   - `test_normalize_message_valid` — test `normalize_message()` with a well-formed raw dict
   - `test_normalize_message_missing_id_raises` — test `normalize_message()` with empty `id` raises `ValueError`

   **Test pattern for Gmail service mock:** Same as calendar — seed a `UserCredentialsORM` row, mock `build()` to return a `MagicMock` service, mock `Credentials` to avoid real auth. The mock service must support chaining: `service.users().messages().list().execute()`, `service.users().history().list().execute()`, etc.

   **Run the full test suite after adding tests:**
   ```bash
   uv run pytest tests/unit/test_google_providers.py -v
   ```

   **Then run the full slice verification:**
   ```bash
   uv run python -c "from helm_providers import GoogleCalendarProvider, GmailProvider, ProviderFactory, CalendarProvider, InboxProvider; print('ok')"
   uv run python -c "from helm_providers.gmail import NormalizedGmailMessage, PullMessagesReport, GmailSendResult, GmailSendError; print('ok')"
   ruff check packages/providers/src/ tests/unit/test_google_providers.py
   ```

## Must-Haves

- [ ] `GmailProvider.__init__` reads `creds.email` for sender address (not env var `GMAIL_USER_EMAIL`)
- [ ] `pull_changed_messages_report` preserves bootstrap fallback when `last_history_cursor=None`
- [ ] `pull_changed_messages_report` preserves recovery fallback on history pull failure
- [ ] `send_reply` validates `to_address` and `body_text` before attempting send
- [ ] `NormalizedGmailMessage`, `PullMessagesReport`, `GmailSendResult`, `GmailSendError` defined in `helm_providers.gmail` with identical shapes to `helm_connectors.gmail`
- [ ] `ProviderFactory.inbox()` returns a working `GmailProvider`
- [ ] All Gmail unit tests pass with mocked API clients
- [ ] All slice-level import smoke tests pass
- [ ] `gauth.get_credentials()` is NOT imported or called

## Verification

- `uv run pytest tests/unit/test_google_providers.py -v` — ALL tests pass (both calendar and Gmail)
- `uv run python -c "from helm_providers import GoogleCalendarProvider, GmailProvider, ProviderFactory, CalendarProvider, InboxProvider; print('ok')"` — succeeds
- `uv run python -c "from helm_providers.gmail import NormalizedGmailMessage, PullMessagesReport, GmailSendResult, GmailSendError; print('ok')"` — succeeds
- `ruff check packages/providers/src/ tests/unit/test_google_providers.py` — 0 errors

## Observability Impact

- Signals added: structlog events `gmail_pull_completed`, `gmail_pull_manual_payload`, `gmail_history_bootstrap_poll`, `gmail_history_pull_failed`, `gmail_send_completed`, `gmail_send_failed` — all ported from existing connector with same event names
- How a future agent inspects this: `uv run pytest tests/unit/test_google_providers.py -v -k gmail` shows Gmail-specific test results
- Failure state exposed: `GmailSendError.failure_class` classifies send failures; `PullMessagesReport.recovery_reason` indicates history cursor issues

## Inputs

- `packages/providers/src/helm_providers/credentials.py` — `build_google_credentials` from T01
- `packages/providers/src/helm_providers/protocols.py` — `InboxProvider` Protocol from T01
- `packages/providers/src/helm_providers/google_calendar.py` — `GoogleCalendarProvider` from T02 (for factory import)
- `packages/providers/src/helm_providers/factory.py` — partially complete from T02 (has `calendar()`, needs `inbox()`)
- `tests/unit/test_google_providers.py` — existing test file from T02 (append Gmail tests)
- `packages/connectors/src/helm_connectors/gmail.py` — **PRIMARY SOURCE.** Port ALL logic from this file: data classes, normalization functions, history polling functions, send_reply. The public method signatures must match exactly so S05 consumers can switch import paths with a single-line change.
- T02 summary — will contain the test file structure and mock patterns established for calendar tests; follow the same patterns for Gmail tests

## Expected Output

- `packages/providers/src/helm_providers/gmail.py` — full `GmailProvider` implementation + transplanted data classes and helpers
- `packages/providers/src/helm_providers/factory.py` — completed with `inbox()` method
- `packages/providers/src/helm_providers/__init__.py` — all public symbols exported
- `tests/unit/test_google_providers.py` — extended with ~10 Gmail unit tests (total ~20 tests in file)
