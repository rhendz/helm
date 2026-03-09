# Helm

Helm is a personal AI leverage system designed to reduce dropped balls, reduce decision fatigue, and increase execution speed.

V1 is intentionally scoped for one user and one primary interface: Telegram.

## V1 Scope

- Opportunity/inbox triage with durable artifacts in Postgres.
- Daily command briefing generated from action items, priorities, and study context.
- Study execution and weakness tracking via structured artifacts.
- Draft generation and approval/snooze loop through Telegram.
- Human-in-the-loop for meaningful outbound actions.

Primary product spec: [`docs/internal/helm-v1.md`](docs/internal/helm-v1.md)

## Architecture Principles

- DB-first and artifact-driven: database is source of truth.
- Modular monorepo: connectors -> agents/workflows -> artifacts -> Telegram/API.
- Personal-first: avoid abstractions for hypothetical multi-tenant use cases.
- Fast iteration over overengineering.

## Monorepo Layout

- `apps/api`: FastAPI internal API and trigger endpoints.
- `apps/worker`: background jobs, schedulers, and workflow execution entrypoint.
- `apps/telegram-bot`: Telegram UX for digest, drafts, approvals, and status commands.
- `packages/domain`: shared domain primitives and value objects.
- `packages/storage`: SQLAlchemy models, session setup, and repositories.
- `packages/connectors`: external ingestion connectors (Gmail/LinkedIn/Telegram adapters).
- `packages/agents`: domain agents (email/linkedin/study/digest).
- `packages/orchestration`: LangGraph graphs and workflow control logic.
- `packages/llm`: OpenAI Responses API client wrappers and prompt interfaces.
- `packages/observability`: structured logging, run instrumentation, and health metadata.
- `migrations`: Alembic migrations.
- `scripts`: local developer commands and seed/smoke helpers.
- `tests`: unit/integration scaffolding.

## Getting Started

### 1. Prerequisites

- Python 3.11+
- Docker + Docker Compose

### 2. Configure env

```bash
cp .env.example .env
```

Fill required values:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_ID`
- Connector credentials when enabling integrations.

### 3. Start local stack

```bash
docker compose up --build
```

Services:

- API: `http://localhost:${API_PORT:-8000}`
- Postgres: `localhost:${POSTGRES_PORT:-5432}`

### 4. Local Python workflow (optional)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

### 5. Gmail credential smoke test (optional)

After setting Gmail env vars in `.env`, run:

```bash
python scripts/check-gmail-auth.py
```

Expected result is a JSON payload with `"ok": true`.

## Initial Commands

- API app: `python -m helm_api.main`
- Worker app: `python -m helm_worker.main`
- Telegram bot: `python -m helm_telegram_bot.main`

## Current Status

Phase 1 bootstrap scaffolding is in place.

- Core app/package boundaries are established.
- Minimal FastAPI/worker/bot entrypoints are wired.
- Compose stack and base env contract exist.
- TODO markers indicate where V1 feature implementation should land.

## Follow-up Priorities

- Implement first Alembic migration from `docs/internal/helm-v1.md` entity model.
- Add Gmail ingestion connector and email triage workflow.
- Add digest generation workflow and Telegram `/digest` command path.
- Add retry/run state dashboards via API endpoints.


- Parallel worktree helper: `scripts/worktree-env.sh`


Linear intake:

- `make linear-projects`
- `make linear-issues`
- `make linear-export`
