# Project

## What This Is

Helm is a single-user personal AI orchestration system, Telegram-first and DB-first. It runs multi-step, approval-gated workflows that connect operator intent to real external systems (Google Calendar, task storage). The core operator loop is: send a task or scheduling request via Telegram → Helm infers semantics → creates internal records → syncs to Calendar → notifies when done.

## Core Value

The operator can add a task through Telegram and trust that it lands on Calendar at the right time, with correct local timezone, without requiring the operator to debug internal state or poll for status.

## Current State

- M001–M003 complete: durable workflow kernel, truth-set cleanup, real Google Calendar OAuth integration with drift detection.
- **M004 complete (S01–S07 all done):**
  - S01–S03: `/task` quick-add with LLM inference, shared timezone/scheduling primitives, immediate execution path.
  - S04: `/status` (pending approvals with `/approve N M` hints, recent completions, OPERATOR_TIMEZONE) and proactive approval notifications implemented.
  - S05: Strict test layer boundaries; E2E safety guards (HELM_E2E + HELM_CALENDAR_TEST_ID fail-fast); calendar_id threaded through full adapter stack; timezone correctness E2E; 436-test baseline.
  - S06: `milestone/M004` merged into `main`; 496 tests passing; watchfiles live reload for worker + bot; ddtrace APM spans on `/task` path (helm.task.run + helm.task.inference) with try/except guard for frozen envs; `/agenda` command (list_today_events, timezone-aware formatting); legacy scheduling stubs removed.
  - S07: Proactive approval notification loop wired into `workflow_runs.run()` (per-run failure isolation, lazy import per D016); `/status` `CommandHandler` registered in `main.py`; 4 new tests; full suite at 500 passed. R108 and R109 validated.
- **M005 complete (S01–S06, SR01 all done):**
  - S01: `users` + `user_credentials` tables with nullable `user_id` FK on 15 domain tables; idempotent `bootstrap_user()` seeding operator row from env vars on startup; `get_credentials()` and `get_user_by_telegram_id()` repository functions. Schema-wipe migration 0014. 10 unit tests.
  - S02: `packages/providers/` (`helm_providers`) package with `CalendarProvider` + `InboxProvider` structural Protocols; `GoogleCalendarProvider` + `GmailProvider` satisfying protocols via gauth bypass (`__new__` + `_service` injection); `build_google_credentials()` with OAuth refresh + DB write-back; `ProviderFactory`; `NormalizedGmailMessage`, `PullMessagesReport`, `GmailSendResult`, `GmailSendError` data classes; `google-workspace-mcp==2.0.1` installed; 42 unit tests.
  - S03: `_build_calendar_adapter()` deleted; worker + bot construct `GoogleCalendarProvider(user_id, db)` from `raw_request` artifact `submitted_by` payload; `_resolve_bootstrap_user_id` (worker) and `_resolve_user_id` (bot) helpers; integration test seeds `UserORM`+`UserCredentialsORM`.
  - S04: `agenda.py` → `GoogleCalendarProvider(user.id, db)` via `SessionLocal` + `get_user_by_telegram_id`; `packages/connectors/google_calendar.py` deleted; `test_google_calendar_adapter.py` and `test_google_calendar_auth.py` deleted; 21 integration tests fixed (time-freeze patches, `_seed_test_user()`, `TELEGRAM_ALLOWED_USER_ID` env setup).
  - S05: Six email pipeline production files migrated from `helm_connectors.gmail` to `helm_providers.gmail`; bootstrap-user provider pattern applied to `email_triage.py`, `email_reconciliation_sweep.py`, `send.py`; `TYPE_CHECKING` guard in `email_messages.py` breaks circular import; `packages/connectors/gmail.py` deleted; 28 email tests pass.
  - S06: `StubCalendarSystemAdapter` + `StubTaskSystemAdapter` moved to `helm_orchestration.stubs`; all 10 `helm_connectors` import sites updated; `packages/connectors/` deleted entirely; `pyproject.toml` cleaned; 5 pre-existing test failures fixed; `scripts/test.sh` exits 0.
  - SR01: 3 stale `"pull_new_messages_report"` monkeypatch targets replaced with `"_pull_new_messages_manual"`; full unit/integration suite at **504 passed, 0 failures**.

## Architecture / Key Patterns

- Python monorepo: `apps/` (api, worker, telegram-bot) and `packages/` (orchestration, storage, providers, agents, llm, observability, runtime). Note: `packages/connectors/` was deleted in M005.
- DB-first: Postgres is the source of truth for workflow state, artifacts, sync records, tasks. `users` + `user_credentials` tables (added M005) support multi-user identity; nullable `user_id` FK on 15 domain tables.
- Custom step-runner in `packages/orchestration` — not LangGraph. Specialist steps registered in `apps/worker/jobs/workflow_runs.py`.
- Worker polls every 30s for runnable steps — background recovery only; operator-triggered actions (`/task`, `/approve`) execute inline immediately.
- Telegram bot is the primary operator surface. Proactive approval push via `TelegramDigestDeliveryService.notify_approval_needed()` fires from the worker notification loop for any `needs_action=True` run.
- Shared scheduling primitives in `packages/orchestration/src/helm_orchestration/scheduling.py` — `compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard`. Both `/task` and weekly scheduling use these; no duplicated logic.
- `OPERATOR_TIMEZONE` (IANA) is required config; validated at startup via `ZoneInfo`. All local time interpretation uses this timezone; UTC conversion only at storage/API boundaries.
- LLM task inference via `packages/llm` (OpenAI `responses.parse`). `LLMClient.infer_task_semantics()` extracts urgency/priority/sizing/confidence from natural language.
- Google Calendar and Gmail I/O via `packages/providers/` (`helm_providers`): `GoogleCalendarProvider(user_id, db)` and `GmailProvider(user_id, db)` satisfy `CalendarProvider`/`InboxProvider` structural Protocol classes; credential injection bypasses `gauth` entirely via `__new__` + direct `_service` assignment using `UserCredentialsORM` tokens from DB. `packages/connectors/` deleted (M005/S06). Stub adapters (`StubCalendarSystemAdapter`, `StubTaskSystemAdapter`) live in `helm_orchestration.stubs`. `ProviderFactory(user_id, db)` is the multi-provider dispatch entry point.
- Bootstrap: `scripts/migrate.sh` calls `run_bootstrap()` after `alembic upgrade head` — seeds operator user + Google credentials from `TELEGRAM_ALLOWED_USER_ID` + `GOOGLE_*` env vars on every startup.
- APM via `ddtrace` (optional dev dep): `helm.task.run` and `helm.task.inference` spans on `/task` path with try/except guard (D018). Structured logs via `structlog` are the primary observability surface.
- Live reload: both `apps/worker` and `apps/telegram-bot` use `python -m watchfiles --filter python` in their run scripts.
- `uv` for dependency management. `uv.lock` present.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract.

## Milestone Sequence

- [x] M001: Helm Orchestration Kernel v1 — Durable workflow kernel with weekly scheduling workflow and shared operator surfaces.
- [x] M002: Helm Truth-Set Cleanup — Strict workflow-engine truth set, removal of stale artifacts, verified task/calendar workflow protection.
- [x] M003: Task/Calendar Productionization — Real Google Calendar OAuth, drift detection, Telegram sync visibility, partial failure handling.
- [x] M004: Foundation Repair — Fix the core task→calendar loop: correct timezone handling, LLM task inference, `/task` quick-add, immediate operator execution, Telegram UX overhaul, strict test boundaries with real E2E calendar coverage, live reload, Datadog. All 7 slices done, 500 tests passing.
- [x] M005: Google MCP Migration + Multi-User Foundation — Replace bespoke Google connectors with google_workspace_mcp, introduce provider protocols, lay multi-user identity foundation. All 7 slices (S01–S06, SR01) done, 504 tests passing.
