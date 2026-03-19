# S05: Replace Gmail I/O in Email Pipeline

**Goal:** Every email pipeline file imports from `helm_providers.gmail` instead of `helm_connectors.gmail`; the old connector file is deleted; all existing email unit tests pass.
**Demo:** `rg "helm_connectors.gmail" apps/ packages/ tests/` returns zero results; `uv run pytest tests/unit/test_email_triage_worker.py tests/unit/test_email_reconciliation_sweep_worker.py tests/unit/test_email_send_recovery.py tests/unit/test_email_service.py tests/unit/test_email_scaffolds.py -v` all pass.

## Must-Haves

- `email_triage.py` uses `GmailProvider.pull_changed_messages_report()` via the bootstrap-user + SessionLocal pattern from S04
- `email_reconciliation_sweep.py` uses `GmailProvider.pull_new_messages_report()` via the same pattern
- `email_agent/send.py` has a module-level `send_reply` function (patchable target) backed by `GmailProvider.send_reply()`
- `email_service.py`, `email_message_ingest.py`, and `email_messages.py` import data classes from `helm_providers.gmail`
- Connector-level tests in `test_email_scaffolds.py` (lines 1–337) are deleted; triage tests (339+) are preserved with updated imports
- `packages/connectors/src/helm_connectors/gmail.py` is deleted
- `rg "helm_connectors.gmail" apps/ packages/ tests/` returns zero hits (excluding comments in `helm_providers/gmail.py`)
- All five email test files pass

## Proof Level

- This slice proves: integration (all email pipeline paths compile and pass unit tests with the new provider)
- Real runtime required: no (unit tests sufficient for import migration; E2E deferred to UAT)
- Human/UAT required: no (UAT covers full email cycle in S06 final-assembly)

## Verification

```bash
# All email-related unit tests pass:
uv run pytest tests/unit/test_email_triage_worker.py \
              tests/unit/test_email_reconciliation_sweep_worker.py \
              tests/unit/test_email_send_recovery.py \
              tests/unit/test_email_service.py \
              tests/unit/test_email_scaffolds.py -v

# No remaining helm_connectors.gmail imports in production or test code:
rg "helm_connectors\.gmail" apps/ packages/agents/ packages/storage/ packages/orchestration/ tests/

# Connector file is deleted:
test ! -f packages/connectors/src/helm_connectors/gmail.py

# Lint clean on all changed files:
ruff check apps/worker/src/helm_worker/jobs/email_triage.py \
           apps/worker/src/helm_worker/jobs/email_reconciliation_sweep.py \
           apps/worker/src/helm_worker/jobs/email_message_ingest.py \
           apps/api/src/helm_api/services/email_service.py \
           packages/agents/src/email_agent/send.py \
           packages/storage/src/helm_storage/repositories/email_messages.py \
           tests/unit/test_email_scaffolds.py \
           tests/unit/test_email_triage_worker.py \
           tests/unit/test_email_reconciliation_sweep_worker.py \
           tests/unit/test_email_send_recovery.py \
           tests/unit/test_email_service.py
```

## Observability / Diagnostics

- Runtime signals: structlog events from `GmailProvider` (`gmail_pull_completed`, `gmail_send_completed`, `gmail_send_failed`) replace the old connector's log events with identical field shapes; new `gmail_provider_constructed` event in worker jobs
- Inspection surfaces: same DB tables and runtime queries — no change from S02's provider observability
- Failure visibility: `_resolve_bootstrap_user_id` raises `RuntimeError` with descriptive message when env var or DB row is missing; `GmailProvider.__init__` raises `RuntimeError("No Google credentials for user_id=N")` on missing credentials
- Redaction constraints: same as S02 — only `user_id` and `expires_at` logged; no tokens or secrets
- **Failure-state diagnostic check:** To verify bootstrap-user failure path is reachable and visible, run: `TELEGRAM_ALLOWED_USER_ID="" uv run python -c "from helm_worker.jobs.email_triage import _resolve_bootstrap_user_id; from unittest.mock import MagicMock; _resolve_bootstrap_user_id(MagicMock())"` — this must raise `RuntimeError: Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set`, confirming that misconfigured environments produce actionable errors rather than silent failures.

## Integration Closure

- Upstream surfaces consumed: `GmailProvider` from `packages/providers/src/helm_providers/gmail.py` (S02); `_resolve_bootstrap_user_id` pattern from `apps/worker/src/helm_worker/jobs/workflow_runs.py` (S04); `SessionLocal` from `packages/storage/src/helm_storage/db.py` (S01)
- New wiring introduced: `email_triage.py` and `email_reconciliation_sweep.py` open `SessionLocal` sessions and construct `GmailProvider` instances at runtime; `email_agent/send.py` does the same inside the `send_reply` wrapper
- What remains before the milestone is truly usable end-to-end: S06 deletes `packages/connectors/` entirely, moves Protocol stubs, and runs the full test suite

## Tasks

- [x] **T01: Rewrite email pipeline production code to use GmailProvider** `est:45m`
  - Why: The six production files that import from `helm_connectors.gmail` need to be migrated to `helm_providers.gmail`. Three files need structural changes (provider construction with bootstrap user pattern); three files need one-line import swaps.
  - Files: `apps/worker/src/helm_worker/jobs/email_triage.py`, `apps/worker/src/helm_worker/jobs/email_reconciliation_sweep.py`, `packages/agents/src/email_agent/send.py`, `apps/worker/src/helm_worker/jobs/email_message_ingest.py`, `apps/api/src/helm_api/services/email_service.py`, `packages/storage/src/helm_storage/repositories/email_messages.py`
  - Do: (1) In `email_triage.py`: add imports for `SessionLocal`, `get_user_by_telegram_id`, `GmailProvider`; add `_resolve_bootstrap_user_id` helper (copied from `workflow_runs.py`); rewrite `run()` to open a `SessionLocal` session, resolve bootstrap user, build `GmailProvider`, call `provider.pull_changed_messages_report(...)`. (2) Same pattern for `email_reconciliation_sweep.py` with `provider.pull_new_messages_report()`. (3) In `email_agent/send.py`: replace `from helm_connectors.gmail import GmailSendError, send_reply` with imports from `helm_providers.gmail`; add `_build_gmail_provider()` helper; keep `send_reply` as a module-level function wrapping `provider.send_reply(...)` with identical keyword signature. (4) One-line import fix in `email_message_ingest.py`, `email_service.py`, and `email_messages.py`. For `email_service.py`, since all callers pass `manual_payload`, import `_normalize_manual_payload` and `PullMessagesReport` from `helm_providers.gmail` and create a local `pull_new_messages_report` wrapper that handles only the manual path.
  - Verify: `ruff check` on all 6 files; `uv run python -c "from helm_worker.jobs import email_triage, email_reconciliation_sweep; from email_agent.send import send_reply, GmailSendError"` succeeds
  - Done when: All six files import from `helm_providers.gmail` only; no `helm_connectors.gmail` imports remain in `apps/` or `packages/agents/` or `packages/storage/`

- [x] **T02: Update tests, delete connector-level tests, and remove gmail.py connector** `est:30m`
  - Why: Test files reference old `helm_connectors.gmail` imports. Worker tests need structural updates to mock the new provider pattern. Connector-level tests in `test_email_scaffolds.py` exercise the old connector's internals and must be deleted. The connector file itself is dead code after T01.
  - Files: `tests/unit/test_email_triage_worker.py`, `tests/unit/test_email_reconciliation_sweep_worker.py`, `tests/unit/test_email_send_recovery.py`, `tests/unit/test_email_service.py`, `tests/unit/test_email_scaffolds.py`, `packages/connectors/src/helm_connectors/gmail.py`
  - Do: (1) Update `test_email_triage_worker.py`: change import to `from helm_providers.gmail import ...`; update monkeypatches to mock `email_triage._build_gmail_provider` returning a mock provider whose `.pull_changed_messages_report()` returns the expected `PullMessagesReport`. (2) Same for `test_email_reconciliation_sweep_worker.py` with `_build_gmail_provider` mock. (3) One-line import fix in `test_email_send_recovery.py` and `test_email_service.py`. (4) In `test_email_scaffolds.py`: delete all connector-level tests (lines 1–337 approximately: everything from `test_normalize_message_contract` through `test_pull_changed_messages_falls_back_when_history_cursor_is_invalid`); keep all triage tests (`test_email_triage_graph_scaffold_result_shape` onward); update import block to use `from helm_providers.gmail import normalize_message`. (5) Delete `packages/connectors/src/helm_connectors/gmail.py`. (6) Verify zero remaining `helm_connectors.gmail` imports.
  - Verify: `uv run pytest tests/unit/test_email_triage_worker.py tests/unit/test_email_reconciliation_sweep_worker.py tests/unit/test_email_send_recovery.py tests/unit/test_email_service.py tests/unit/test_email_scaffolds.py -v` all pass; `rg "helm_connectors\.gmail" apps/ packages/agents/ packages/storage/ tests/` returns nothing; `ruff check` on all test files clean
  - Done when: All five test files pass; connector file is deleted; `rg "helm_connectors.gmail"` returns zero hits in production and test code (only comments in `helm_providers/gmail.py` are acceptable)

## Files Likely Touched

- `apps/worker/src/helm_worker/jobs/email_triage.py`
- `apps/worker/src/helm_worker/jobs/email_reconciliation_sweep.py`
- `apps/worker/src/helm_worker/jobs/email_message_ingest.py`
- `apps/api/src/helm_api/services/email_service.py`
- `packages/agents/src/email_agent/send.py`
- `packages/storage/src/helm_storage/repositories/email_messages.py`
- `tests/unit/test_email_triage_worker.py`
- `tests/unit/test_email_reconciliation_sweep_worker.py`
- `tests/unit/test_email_send_recovery.py`
- `tests/unit/test_email_service.py`
- `tests/unit/test_email_scaffolds.py`
- `packages/connectors/src/helm_connectors/gmail.py` (deleted)
