# Helm Tech Stack

## Overview

Helm is a Python 3.11 monorepo built as a small internal distributed system: a FastAPI app, a polling worker, a polling Telegram bot, and a Postgres database. The runtime is container-friendly via Docker Compose, but local development is primarily driven through `uv` and shell scripts.

## Languages And Packaging

- Primary language: Python 3.11+, declared in `pyproject.toml`.
- Packaging: setuptools editable install with multiple source roots from `apps/*/src` and `packages/*/src` in `pyproject.toml`.
- Dependency management and command execution: `uv`, used by `scripts/bootstrap.sh`, `scripts/lint.sh`, `scripts/test.sh`, and the `Makefile`.
- Lockfile: `uv.lock`.

## Application Topology

- API service: FastAPI app in `apps/api/src/helm_api/main.py`.
- Worker service: long-running polling loop in `apps/worker/src/helm_worker/main.py`.
- Telegram bot: polling bot process in `apps/telegram-bot/src/helm_telegram_bot/main.py`.
- Shared runtime/config base: `packages/runtime/src/helm_runtime/config.py`.
- Compose topology: `docker-compose.yml` runs `postgres`, one-shot `migrate`, `api`, `worker`, and `telegram-bot`.

## Web And Transport Layer

- HTTP framework: FastAPI in `apps/api/src/helm_api/main.py` and routers under `apps/api/src/helm_api/routers/`.
- ASGI server: Uvicorn, started by `scripts/run-api.sh`.
- Telegram transport: `python-telegram-bot` in `apps/telegram-bot/src/helm_telegram_bot/main.py`.
- Bot delivery path for digests: `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py`.
- Current Telegram mode: polling via `application.run_polling()` in `apps/telegram-bot/src/helm_telegram_bot/main.py`.

## Data And Persistence

- Primary database: PostgreSQL, configured in `.env.example` and provisioned in `docker-compose.yml`.
- DB access layer: SQLAlchemy 2.x in `packages/storage/src/helm_storage/db.py`.
- Driver: `psycopg[binary]`, referenced by `pyproject.toml` and the default `DATABASE_URL`.
- ORM models: `packages/storage/src/helm_storage/models.py`.
- Repository pattern: SQLAlchemy repositories under `packages/storage/src/helm_storage/repositories/`.
- Schema migration tool: Alembic in `migrations/`, configured by `alembic.ini` and `migrations/env.py`.

## Workflow And Agent Runtime

- Workflow engine: LangGraph is a real dependency and is used by the email triage flow in `packages/agents/src/email_agent/triage.py`.
- Agent runtime adapter: `packages/agents/src/email_agent/adapters/helm_runtime.py` bridges workflow logic to storage repositories.
- Worker job registry: `apps/worker/src/helm_worker/jobs/registry.py`.
- Implemented worker jobs: email triage, digest, study, replay, and scheduled thread tasks under `apps/worker/src/helm_worker/jobs/`.
- Orchestration package boundary exists in `packages/orchestration/README.md`, but most implemented workflow logic currently lives in `packages/agents/src/email_agent/`.

## LLM Layer

- Model provider: OpenAI.
- Client wrapper: `packages/llm/src/helm_llm/client.py`.
- API style: OpenAI Responses API via `OpenAI(...).responses.create(...)` in `packages/llm/src/helm_llm/client.py`.
- Model selection: `OPENAI_MODEL` env var in `.env.example`.
- Current usage maturity: wrapper exists and is concrete, but the repository still contains scaffold/TODO language around structured prompt contracts.

## Observability And Runtime State

- Logging: standard library `logging` plus `structlog` JSON rendering in `packages/observability/src/helm_observability/logging.py`.
- Run tracing/persistence: agent run lifecycle stored via `packages/observability/src/helm_observability/agent_runs.py`.
- Health endpoint: `/healthz` in `apps/api/src/helm_api/main.py`.
- Failure inspection endpoints: status/debug routes under `apps/api/src/helm_api/routers/status.py`.

## Configuration

- Environment-driven config: Pydantic Settings in `packages/runtime/src/helm_runtime/config.py`.
- Shared env contract: `.env.example`.
- App-specific settings:
  - API: `apps/api/src/helm_api/config.py`
  - Worker: `apps/worker/src/helm_worker/config.py`
  - Telegram bot: `apps/telegram-bot/src/helm_telegram_bot/config.py`

## Developer Tooling

- Linting: Ruff via `scripts/lint.sh`.
- Tests: Pytest via `scripts/test.sh`.
- Async tests: `pytest-asyncio` in `pyproject.toml`.
- Pre-commit support: `pre-commit` listed in `pyproject.toml`.
- Formatting helper: `scripts/format.sh`.
- Smoke/dev helpers: `scripts/smoke.sh`, `scripts/doctor.sh`, `scripts/bootstrap.sh`.
- Make targets wrap the common workflows in `Makefile`.

## Container And Local Runtime Notes

- Base image: `python:3.11-slim` in `Dockerfile`.
- Containers install the project with dev extras using `pip install -e .[dev]` in `Dockerfile`.
- App startup scripts manually set `PYTHONPATH` rather than relying purely on installed package resolution:
  - `scripts/run-api.sh`
  - `scripts/run-worker.sh`
  - `scripts/run-telegram-bot.sh`
- API container runs with Uvicorn `--reload` in `scripts/run-api.sh`, which is useful for development but is not a production-oriented server setup.

## Testing Shape

- Unit and integration tests are both under `tests/`.
- API route tests use FastAPI `TestClient`, for example `tests/integration/test_routes.py`.
- Storage-heavy unit tests use in-memory/local SQLAlchemy engines rather than requiring external services, for example `tests/unit/test_storage_repositories.py`.

## Practical Takeaways

- The repository is already a coherent Python monorepo with explicit service boundaries and a real Postgres-backed artifact model.
- The most concrete implemented stack paths today are FastAPI, SQLAlchemy/Postgres, Telegram polling, LangGraph-based email triage, and structlog-backed observability.
- `packages/orchestration` and parts of `packages/llm` are present as architectural boundaries, but the implemented behavior is still concentrated in the app, agent, storage, and connector layers.
