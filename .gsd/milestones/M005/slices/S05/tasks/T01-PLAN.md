---
estimated_steps: 7
estimated_files: 6
---

# T01: Rewrite email pipeline production code to use GmailProvider

**Slice:** S05 — Replace Gmail I/O in Email Pipeline
**Milestone:** M005

## Description

Migrate all six production files that import from `helm_connectors.gmail` to use `helm_providers.gmail` instead. Three files need structural changes (adding the bootstrap-user + SessionLocal + GmailProvider pattern); three files need one-line import path swaps.

The S04 pattern for provider construction is: open a `SessionLocal()` session, call `_resolve_bootstrap_user_id(session)` to get the user ID, then construct `GmailProvider(user_id, session)`. Copy this pattern from `apps/worker/src/helm_worker/jobs/workflow_runs.py`.

**Critical constraint for `email_agent/send.py`:** The `send_reply` function must remain a module-level callable with the exact signature `send_reply(*, provider_thread_id, to_address, subject, body_text) -> GmailSendResult`. Multiple test files patch `"email_agent.send.send_reply"` — this monkeypatch target must continue to work.

**Critical constraint for `email_service.py`:** All three callers of `pull_new_messages_report` pass `manual_payload=...`. The `GmailProvider.pull_new_messages_report(manual_payload=...)` method works for this path but requires constructing a provider (which needs DB credentials). Instead, import `_normalize_manual_payload` and `PullMessagesReport` from `helm_providers.gmail` and create a local `pull_new_messages_report(manual_payload=...)` that delegates to `_normalize_manual_payload`. This avoids needing a provider for the manual-only path.

## Steps

1. **Rewrite `apps/worker/src/helm_worker/jobs/email_triage.py`:**
   - Remove: `from helm_connectors.gmail import pull_changed_messages_report`
   - Add imports: `import os`, `from helm_providers.gmail import GmailProvider`, `from helm_storage.db import SessionLocal`, `from helm_storage.repositories.users import get_user_by_telegram_id`
   - Add `_resolve_bootstrap_user_id(db: Session) -> int` helper — copy the exact implementation from `apps/worker/src/helm_worker/jobs/workflow_runs.py` lines 129–145
   - Add `_build_gmail_provider(db: Session, user_id: int) -> GmailProvider` helper that constructs and returns `GmailProvider(user_id, db)` with a structlog info event
   - Rewrite `run()`: wrap the body in `with SessionLocal() as session:`, call `user_id = _resolve_bootstrap_user_id(session)`, call `provider = _build_gmail_provider(session, user_id)`, replace `pull_changed_messages_report(last_history_cursor=config.last_history_cursor)` with `provider.pull_changed_messages_report(last_history_cursor=config.last_history_cursor)`. Keep all existing logic (runtime, config, ingest, cursor update, logging) unchanged.

2. **Rewrite `apps/worker/src/helm_worker/jobs/email_reconciliation_sweep.py`:**
   - Same pattern as step 1 but using `provider.pull_new_messages_report()` instead of `provider.pull_changed_messages_report(...)`.
   - Remove: `from helm_connectors.gmail import pull_new_messages_report`
   - Add same imports. Add same `_resolve_bootstrap_user_id` and `_build_gmail_provider` helpers.
   - Rewrite `run()` with SessionLocal wrapper and provider construction.

3. **Rewrite `packages/agents/src/email_agent/send.py`:**
   - Remove: `from helm_connectors.gmail import GmailSendError, send_reply`
   - Add: `import os`, `from helm_providers.gmail import GmailProvider, GmailSendError`, `from helm_storage.db import SessionLocal`, `from helm_storage.repositories.users import get_user_by_telegram_id`
   - Add `_resolve_bootstrap_user_id(db)` helper (same as above)
   - Add `_build_gmail_provider(db, user_id)` helper
   - Create a new module-level `send_reply` function with the **exact same signature**:
     ```python
     def send_reply(
         *,
         provider_thread_id: str,
         to_address: str,
         subject: str,
         body_text: str,
     ) -> GmailSendResult:
         with SessionLocal() as session:
             user_id = _resolve_bootstrap_user_id(session)
             provider = _build_gmail_provider(session, user_id)
             return provider.send_reply(
                 provider_thread_id=provider_thread_id,
                 to_address=to_address,
                 subject=subject,
                 body_text=body_text,
             )
     ```
   - Also add `from helm_providers.gmail import GmailSendResult` so tests that import `GmailSendResult` from `email_agent.send` (if any) still work. Actually, verify first — `GmailSendResult` is imported from `helm_connectors.gmail` in test files, not from `email_agent.send`. The current `send.py` does not re-export `GmailSendResult`. So just ensure `GmailSendError` is importable from `email_agent.send` (it is, since it's used in the try/except).

4. **Fix `apps/worker/src/helm_worker/jobs/email_message_ingest.py` (1-line):**
   - Change line 8: `from helm_connectors.gmail import NormalizedGmailMessage` → `from helm_providers.gmail import NormalizedGmailMessage`

5. **Fix `apps/api/src/helm_api/services/email_service.py`:**
   - Remove: `from helm_connectors.gmail import pull_new_messages_report` (line 30)
   - Add: `from helm_providers.gmail import PullMessagesReport, _normalize_manual_payload` and `from helm_observability.logging import get_logger`
   - Add a local wrapper function:
     ```python
     def _pull_new_messages_manual(messages: list[dict]) -> PullMessagesReport:
         """Normalize a manual payload without constructing a GmailProvider."""
         return _normalize_manual_payload(
             messages,
             logger=get_logger("helm_api.services.email_service"),
             next_history_cursor=None,
             mode="manual",
         )
     ```
   - Replace the three call sites: `pull_new_messages_report(manual_payload=[dict(item) for item in messages])` → `_pull_new_messages_manual([dict(item) for item in messages])`

6. **Fix `packages/storage/src/helm_storage/repositories/email_messages.py` (1-line):**
   - Change line 3: `from helm_connectors.gmail import NormalizedGmailMessage` → `from helm_providers.gmail import NormalizedGmailMessage`

7. **Lint check all 6 files:**
   ```bash
   ruff check apps/worker/src/helm_worker/jobs/email_triage.py \
              apps/worker/src/helm_worker/jobs/email_reconciliation_sweep.py \
              apps/worker/src/helm_worker/jobs/email_message_ingest.py \
              apps/api/src/helm_api/services/email_service.py \
              packages/agents/src/email_agent/send.py \
              packages/storage/src/helm_storage/repositories/email_messages.py
   ```

## Must-Haves

- [ ] `email_triage.py` builds `GmailProvider` via bootstrap-user pattern and calls `provider.pull_changed_messages_report(...)`
- [ ] `email_reconciliation_sweep.py` builds `GmailProvider` via bootstrap-user pattern and calls `provider.pull_new_messages_report()`
- [ ] `email_agent/send.py` has module-level `send_reply(*, provider_thread_id, to_address, subject, body_text)` that wraps `GmailProvider.send_reply(...)`
- [ ] `email_agent/send.py` imports `GmailSendError` from `helm_providers.gmail` (used in the try/except in `send_approved_draft`)
- [ ] `email_service.py` uses a local wrapper for manual-payload normalization, no longer imports from `helm_connectors.gmail`
- [ ] `email_message_ingest.py` imports `NormalizedGmailMessage` from `helm_providers.gmail`
- [ ] `email_messages.py` (storage repo) imports `NormalizedGmailMessage` from `helm_providers.gmail`
- [ ] Zero `helm_connectors.gmail` imports remain in `apps/` and `packages/agents/` and `packages/storage/`
- [ ] All 6 files pass `ruff check`

## Verification

- `ruff check` on all 6 files returns 0 errors
- `rg "helm_connectors\.gmail" apps/ packages/agents/ packages/storage/` returns nothing
- `uv run python -c "from helm_worker.jobs import email_triage; from helm_worker.jobs import email_reconciliation_sweep; from email_agent.send import send_reply, GmailSendError; from helm_worker.jobs.email_message_ingest import NormalizedGmailMessage"` succeeds

## Inputs

- `packages/providers/src/helm_providers/gmail.py` — S02 output: `GmailProvider`, `NormalizedGmailMessage`, `PullMessagesReport`, `GmailSendResult`, `GmailSendError`, `normalize_message`, `_normalize_manual_payload`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — S04 output: `_resolve_bootstrap_user_id` and `_build_calendar_provider` patterns to copy
- `packages/storage/src/helm_storage/db.py` — `SessionLocal` sessionmaker
- `packages/storage/src/helm_storage/repositories/users.py` — `get_user_by_telegram_id`

## Expected Output

- `apps/worker/src/helm_worker/jobs/email_triage.py` — rewritten with GmailProvider construction; no `helm_connectors` imports
- `apps/worker/src/helm_worker/jobs/email_reconciliation_sweep.py` — same pattern
- `packages/agents/src/email_agent/send.py` — module-level `send_reply` wrapper backed by GmailProvider; `GmailSendError` imported from `helm_providers.gmail`
- `apps/worker/src/helm_worker/jobs/email_message_ingest.py` — import path fixed
- `apps/api/src/helm_api/services/email_service.py` — local manual-payload wrapper; no connector import
- `packages/storage/src/helm_storage/repositories/email_messages.py` — import path fixed

## Observability Impact

**New runtime signals introduced:**
- `gmail_provider_constructed` — emitted in `_build_gmail_provider()` in both `email_triage.py` and `email_reconciliation_sweep.py`. Fields: `user_id` (int), `source="db_credentials"`. Replaces implicit provider construction in the old connector with an explicit, observable event.

**Inherited signals (unchanged behavior):**
- `email_triage_job_tick` / `email_triage_job_completed` — log events remain identical; same fields.
- `email_reconciliation_sweep_tick` / `email_reconciliation_sweep_completed` — identical to before.
- `gmail_pull_completed`, `gmail_pull_manual_payload`, `gmail_pull_manual_payload_failures` — emitted by `GmailProvider` internals (S02); same field shapes as old connector.
- `gmail_send_completed`, `gmail_send_failed` — emitted by `GmailProvider.send_reply()` internally.

**Failure visibility:**
- Missing `TELEGRAM_ALLOWED_USER_ID` env var: `_resolve_bootstrap_user_id` raises `RuntimeError("Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set")`.
- Missing DB user row: raises `RuntimeError(f"Bootstrap user not found: no user with telegram_user_id=N")`.
- Missing Google credentials: `GmailProvider.__init__` raises `RuntimeError("No Google credentials for user_id=N")`.
- Manual payload normalization failures: `_pull_new_messages_manual` logs `gmail_pull_manual_payload_failures` with `failure_counts` dict.

**How to inspect at runtime:**
1. Grep worker logs for `gmail_provider_constructed` to confirm bootstrap user was resolved and provider built.
2. If bootstrap fails: `RuntimeError` appears in job exception trace before `email_triage_job_tick` fires.
3. Manual ingest: `gmail_pull_manual_payload` log shows `mode=manual` and message count.
