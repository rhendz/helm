---
estimated_steps: 7
estimated_files: 6
---

# T02: Update tests, delete connector-level tests, and remove gmail.py connector

**Slice:** S05 — Replace Gmail I/O in Email Pipeline
**Milestone:** M005

## Description

After T01 rewrote the production code, the test files still import from `helm_connectors.gmail`. This task updates all five email test files and deletes the old connector file.

Three categories of work:
1. **Structural test rewrites** (2 files): `test_email_triage_worker.py` and `test_email_reconciliation_sweep_worker.py` currently monkeypatch `email_triage.pull_changed_messages_report` and `email_reconciliation_sweep.pull_new_messages_report`. After T01, those module-level names no longer exist — instead, the jobs build a `GmailProvider` via `_build_gmail_provider`. Tests must now mock `_build_gmail_provider` to return a mock provider.
2. **Import-path fixes** (2 files): `test_email_send_recovery.py` and `test_email_service.py` need one-line import swaps from `helm_connectors.gmail` to `helm_providers.gmail`.
3. **Test cleanup + connector deletion** (2 files): `test_email_scaffolds.py` has connector-level tests (lines 1–337 approximately) that exercise the old connector's internal functions (`_build_gmail_service`, env-var configuration, polling). These must be deleted. The surviving triage tests (line 339+) need import fixes. Then `packages/connectors/src/helm_connectors/gmail.py` is deleted.

## Steps

1. **Rewrite `tests/unit/test_email_triage_worker.py`:**
   - Change line 3: `from helm_connectors.gmail import NormalizedGmailMessage, PullMessagesReport` → `from helm_providers.gmail import NormalizedGmailMessage, PullMessagesReport`
   - Add: `from unittest.mock import MagicMock`
   - In both test functions, after T01's rewrite of `email_triage.py`, the `run()` function now calls `_build_gmail_provider(session, user_id)` internally (inside a `SessionLocal()` context). The tests need to:
     a. Still monkeypatch `email_triage.build_email_agent_runtime` (unchanged)
     b. Replace `monkeypatch.setattr(email_triage, "pull_changed_messages_report", ...)` with a mock of `email_triage._build_gmail_provider`
     c. The mock should return a `MagicMock()` whose `.pull_changed_messages_report(...)` returns the `PullMessagesReport` that was previously returned directly
     d. Also monkeypatch `email_triage._resolve_bootstrap_user_id` to return `1` (avoids needing `TELEGRAM_ALLOWED_USER_ID` env var and a real DB user row)
     e. Also monkeypatch `email_triage.SessionLocal` to return a `MagicMock()` context manager (avoids needing a real DB session for provider construction)
   - Example monkeypatch pattern for the first test:
     ```python
     mock_provider = MagicMock()
     mock_provider.pull_changed_messages_report.return_value = PullMessagesReport(
         messages=[...],
         failure_counts={},
         next_history_cursor="cursor-2",
         mode="history",
     )
     monkeypatch.setattr(email_triage, "_resolve_bootstrap_user_id", lambda db: 1)
     mock_session_cm = MagicMock()
     mock_session_cm.__enter__ = MagicMock(return_value=MagicMock())
     mock_session_cm.__exit__ = MagicMock(return_value=False)
     monkeypatch.setattr(email_triage, "SessionLocal", lambda: mock_session_cm)
     monkeypatch.setattr(email_triage, "_build_gmail_provider", lambda db, user_id: mock_provider)
     ```
   - The key: the rest of the test logic (assertions on EmailMessageORM, cursor updates) should remain unchanged. The only change is HOW the gmail function is mocked.

2. **Rewrite `tests/unit/test_email_reconciliation_sweep_worker.py`:**
   - Same pattern as step 1, but mock `email_reconciliation_sweep._build_gmail_provider` and the mock provider's `.pull_new_messages_report()`.
   - Change import to `from helm_providers.gmail import NormalizedGmailMessage, PullMessagesReport`
   - Add `from unittest.mock import MagicMock`
   - Mock `_resolve_bootstrap_user_id`, `SessionLocal`, and `_build_gmail_provider` on the `email_reconciliation_sweep` module.

3. **Fix `tests/unit/test_email_send_recovery.py` (1-line):**
   - Change line 6: `from helm_connectors.gmail import GmailSendResult` → `from helm_providers.gmail import GmailSendResult`

4. **Fix `tests/unit/test_email_service.py` (1-line):**
   - Change line 21: `from helm_connectors.gmail import GmailSendError, GmailSendResult` → `from helm_providers.gmail import GmailSendError, GmailSendResult`

5. **Clean up `tests/unit/test_email_scaffolds.py`:**
   - Delete the import block at the top that references `helm_connectors`:
     - Remove `from helm_connectors import gmail`
     - Remove `from helm_connectors.gmail import (normalize_message, pull_changed_messages_report, pull_new_messages, pull_new_messages_report)`
   - Add: `from helm_providers.gmail import normalize_message`
   - Delete ALL connector-level test functions (everything before `test_email_triage_graph_scaffold_result_shape`):
     - `test_normalize_message_contract` (line 35)
     - `test_normalize_message_requires_message_id` (line 56)
     - `test_pull_new_messages_manual_payload_normalizes` (line 61)
     - `test_pull_new_messages_manual_payload_records_failures_and_keeps_valid` (line 78)
     - `test_pull_new_messages_returns_empty_when_unconfigured` (line 91)
     - `test_pull_new_messages_polling_normalizes_provider_payload` (line 99)
     - `test_pull_changed_messages_history_normalizes_provider_payload_and_cursor` (line 163)
     - `test_pull_changed_messages_bootstraps_to_poll_when_cursor_missing` (line 241)
     - `test_pull_changed_messages_falls_back_when_history_cursor_is_invalid` (line 285)
   - Keep everything from `test_email_triage_graph_scaffold_result_shape` (line 339) onward
   - The surviving tests use `normalize_message(...)` which is a module-level function in `helm_providers.gmail` with identical behavior — the import fix is sufficient

6. **Delete `packages/connectors/src/helm_connectors/gmail.py`:**
   - `rm packages/connectors/src/helm_connectors/gmail.py`
   - Verify no other files in `packages/connectors/src/helm_connectors/__init__.py` import from `gmail`
   - Run: `rg "helm_connectors\.gmail" apps/ packages/ tests/` — should return zero results (comments in `helm_providers/gmail.py` are acceptable but that file path is not in the grep scope)

7. **Full verification:**
   ```bash
   uv run pytest tests/unit/test_email_triage_worker.py \
                 tests/unit/test_email_reconciliation_sweep_worker.py \
                 tests/unit/test_email_send_recovery.py \
                 tests/unit/test_email_service.py \
                 tests/unit/test_email_scaffolds.py -v

   ruff check tests/unit/test_email_triage_worker.py \
              tests/unit/test_email_reconciliation_sweep_worker.py \
              tests/unit/test_email_send_recovery.py \
              tests/unit/test_email_service.py \
              tests/unit/test_email_scaffolds.py

   rg "helm_connectors\.gmail" apps/ packages/agents/ packages/storage/ tests/
   test ! -f packages/connectors/src/helm_connectors/gmail.py
   ```

## Must-Haves

- [ ] `test_email_triage_worker.py` mocks `_build_gmail_provider` and `_resolve_bootstrap_user_id`; both tests pass
- [ ] `test_email_reconciliation_sweep_worker.py` mocks same pattern; both tests pass
- [ ] `test_email_send_recovery.py` imports from `helm_providers.gmail`; tests pass
- [ ] `test_email_service.py` imports from `helm_providers.gmail`; tests pass
- [ ] `test_email_scaffolds.py` has no connector-level tests; surviving triage tests pass with `helm_providers.gmail` imports
- [ ] `packages/connectors/src/helm_connectors/gmail.py` is deleted
- [ ] `rg "helm_connectors\.gmail" apps/ packages/agents/ packages/storage/ tests/` returns zero results

## Verification

- `uv run pytest tests/unit/test_email_triage_worker.py tests/unit/test_email_reconciliation_sweep_worker.py tests/unit/test_email_send_recovery.py tests/unit/test_email_service.py tests/unit/test_email_scaffolds.py -v` — all pass
- `rg "helm_connectors\.gmail" apps/ packages/agents/ packages/storage/ tests/` — zero results
- `ruff check` on all 5 test files — 0 errors
- `test ! -f packages/connectors/src/helm_connectors/gmail.py` — file does not exist

## Observability Impact

**Signals changed:** No new structlog events are added in this task. The signals introduced in T01 (`gmail_provider_constructed`, `email_triage_job_tick`, `email_reconciliation_sweep_tick`) are exercised by the updated tests — confirming they fire correctly when the provider is built.

**How a future agent inspects this task's output:**
- `rg "helm_connectors\.gmail" apps/ packages/agents/ packages/storage/ tests/` — must return zero results; any hit means a file was missed
- `test ! -f packages/connectors/src/helm_connectors/gmail.py` — connector deletion confirmation
- `uv run pytest tests/unit/test_email_triage_worker.py tests/unit/test_email_reconciliation_sweep_worker.py -v` — verifies the monkeypatching of `_build_gmail_provider` and `_resolve_bootstrap_user_id` works correctly

**Failure-state visibility:**
- If `_build_gmail_provider` is not properly monkeypatched, the worker tests will attempt to open a real `SessionLocal` connection and fail with a database connectivity error (e.g., `OperationalError: could not connect to server`)
- If `_resolve_bootstrap_user_id` is not monkeypatched, tests will fail with `RuntimeError: Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set` — which is actually the correct runtime failure signal confirming the error path works
- To verify the bootstrap failure path is reachable in production: `TELEGRAM_ALLOWED_USER_ID="" uv run python -c "from helm_worker.jobs.email_triage import _resolve_bootstrap_user_id; from unittest.mock import MagicMock; _resolve_bootstrap_user_id(MagicMock())"` — must raise `RuntimeError: Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set`

## Inputs

- T01 output: all 6 production files rewritten to use `helm_providers.gmail`
- `apps/worker/src/helm_worker/jobs/email_triage.py` — T01 added `_build_gmail_provider`, `_resolve_bootstrap_user_id`, `SessionLocal` as module-level names
- `apps/worker/src/helm_worker/jobs/email_reconciliation_sweep.py` — same pattern
- `packages/providers/src/helm_providers/gmail.py` — S02 output: all data classes and `normalize_message` function

## Expected Output

- `tests/unit/test_email_triage_worker.py` — updated mock pattern for provider construction
- `tests/unit/test_email_reconciliation_sweep_worker.py` — same
- `tests/unit/test_email_send_recovery.py` — import path fixed
- `tests/unit/test_email_service.py` — import path fixed
- `tests/unit/test_email_scaffolds.py` — connector tests deleted, triage tests preserved with fixed imports
- `packages/connectors/src/helm_connectors/gmail.py` — deleted
