# Helm External Integrations

## Overview

The repository currently integrates with a small set of external systems: PostgreSQL for durable state, Telegram for the primary operator interface, OpenAI for model calls, Gmail for inbound email ingestion, Linear for issue/project automation, and GitHub CLI as a local dependency of one Linear reconciliation workflow.

## Integration Map

| System | Purpose | Code paths | Config |
| --- | --- | --- | --- |
| PostgreSQL | Source of truth for artifacts and run state | `packages/storage/src/helm_storage/db.py`, `packages/storage/src/helm_storage/models.py`, `migrations/env.py`, `docker-compose.yml` | `DATABASE_URL`, `POSTGRES_*` in `.env.example` |
| Telegram Bot API | Primary user interface for commands, approvals, and digest delivery | `apps/telegram-bot/src/helm_telegram_bot/main.py`, `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, `TELEGRAM_WEBHOOK_URL` in `.env.example` |
| OpenAI API | LLM summarization/model calls | `packages/llm/src/helm_llm/client.py` | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS` in `.env.example` |
| Gmail API | Pull inbound email and normalize messages for triage | `packages/connectors/src/helm_connectors/gmail.py`, `scripts/check-gmail-auth.py`, `apps/worker/src/helm_worker/jobs/email_triage.py` | `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_USER_EMAIL` in `.env.example` |
| Linear GraphQL API | Team/project/issue intake and PR-to-ticket drift checks | `scripts/linear_intake.py`, `packages/runtime/src/helm_runtime/pr_linear_reconcile.py` | `LINEAR_API_KEY`, `LINEAR_TEAM_KEY` in `.env.example` |
| GitHub CLI (`gh`) | Fetch merged PRs for Linear reconciliation | `packages/runtime/src/helm_runtime/pr_linear_reconcile.py` | local authenticated `gh` environment |

## PostgreSQL

### What is implemented

- Postgres is the canonical system of record for contacts, action items, drafts, digests, email artifacts, scheduled tasks, and agent runs in `packages/storage/src/helm_storage/models.py`.
- SQLAlchemy sessions are created in `packages/storage/src/helm_storage/db.py`.
- Alembic migrations live in `migrations/versions/`.
- Local compose bootstraps Postgres and runs migrations before starting app services in `docker-compose.yml`.

### How the rest of the system uses it

- API services read persisted artifacts through repository-backed service modules under `apps/api/src/helm_api/services/`.
- Worker jobs persist and update run state and artifact state, for example `apps/worker/src/helm_worker/jobs/email_triage.py`.
- Telegram command handlers read and transition persisted draft/action artifacts through `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py`.

### Practical notes

- This is the most mature integration in the repo.
- The product spec’s “DB-first artifact model” is reflected in live code, not just documentation.

## Telegram Bot API

### What is implemented

- Bot bootstrap and command registration are in `apps/telegram-bot/src/helm_telegram_bot/main.py`.
- Registered commands: `/start`, `/digest`, `/actions`, `/drafts`, `/study`, `/approve`, `/snooze`.
- Direct message delivery for digests uses `telegram.Bot.send_message` in `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py`.

### Access control and mode

- V1 user gating is enforced with `TELEGRAM_ALLOWED_USER_ID`, referenced in config and command guards.
- The bot currently runs in polling mode through `application.run_polling()` in `apps/telegram-bot/src/helm_telegram_bot/main.py`.
- `TELEGRAM_WEBHOOK_URL` exists in `.env.example`, but this repository snapshot does not show webhook wiring in the bot runtime.

### Practical notes

- Telegram is a live product-facing integration, not just planned architecture.
- Approval and snooze flows are implemented against stored draft artifacts, which keeps outbound actions human-supervised.

## OpenAI API

### What is implemented

- `packages/llm/src/helm_llm/client.py` instantiates `OpenAI` and calls the Responses API.
- The wrapper currently exposes a `summarize` method that sends a simple user prompt and returns `response.output_text`.

### Current maturity

- The integration is real but thin.
- Timeout config appears in `.env.example`, but the current client implementation does not pass `OPENAI_TIMEOUT_SECONDS` into the SDK call.
- The codebase still treats prompt contracts and structured outputs as follow-up work.

### Practical notes

- OpenAI is the only LLM provider wired in code.
- The wrapper is isolated enough that changing model usage later should be localized to `packages/llm/src/helm_llm/client.py` and its callers.

## Gmail API

### What is implemented

- Gmail connector logic lives in `packages/connectors/src/helm_connectors/gmail.py`.
- It uses OAuth refresh-token credentials from env vars, refreshes via Google Auth, and builds a Gmail API client via `googleapiclient.discovery.build`.
- It lists recent messages, fetches full payloads, extracts headers/body, normalizes them, and returns typed message records.
- Worker integration point: `apps/worker/src/helm_worker/jobs/email_triage.py` pulls messages and sends them into the email triage workflow.
- Credential smoke test: `scripts/check-gmail-auth.py`.

### Dependency shape

- Google client libraries are only listed in `[project.optional-dependencies].dev` in `pyproject.toml`.
- The runtime connector handles missing Google dependencies by logging and returning no messages rather than crashing.

### Practical notes

- This is a partially mature integration: it is wired to real Gmail APIs, but it still carries scaffold language in docs and some failure paths.
- The connector is inbound/read-only; there is no implemented Gmail send path in this repository snapshot.

## Linear GraphQL API

### What is implemented

- `scripts/linear_intake.py` queries Linear teams, projects, and issues and can export a Markdown inbox snapshot.
- `packages/runtime/src/helm_runtime/pr_linear_reconcile.py` fetches Linear issues/comments, correlates them with merged PRs, and can detect workflow drift such as missing completion state or missing merge SHA comments.
- Both modules call Linear directly over HTTPS using `urllib.request` against `https://api.linear.app/graphql`.

### Scope and usage

- Linear is currently an operator/developer workflow integration, not a product runtime dependency for the user-facing app/bot flows.
- The `Makefile` exposes convenience commands:
  - `make linear-projects`
  - `make linear-issues`
  - `make linear-export`

### Practical notes

- Auth is a raw API key in `LINEAR_API_KEY`; there is no higher-level SDK abstraction here.
- This integration is useful for repo operations and planning hygiene, but it is separate from the main product artifact loop.

## GitHub CLI

### What is implemented

- `packages/runtime/src/helm_runtime/pr_linear_reconcile.py` shells out to `gh pr list --state merged ...` to fetch merged pull requests.

### Why it matters

- The Linear reconciliation workflow is not fully self-contained; it depends on a locally installed and authenticated GitHub CLI.
- This is an integration dependency for engineering workflow automation, not for Helm’s product runtime.

## Integration Boundaries And Gaps

- The product runtime depends most directly on PostgreSQL, Telegram, Gmail, and OpenAI.
- Linear and GitHub CLI are engineering workflow integrations around planning/reconciliation.
- `TELEGRAM_WEBHOOK_URL` is present in config but not wired in the bot runtime shown here.
- `OPENAI_TIMEOUT_SECONDS` is configured but not yet consumed by `packages/llm/src/helm_llm/client.py`.
- Gmail read access is implemented; outbound email sending is not present in the current codebase snapshot.
- The orchestration package boundary exists, but most external-system calls currently happen directly from app/service/connector packages rather than through a dedicated integration facade.
