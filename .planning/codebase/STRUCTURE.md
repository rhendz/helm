# Structure

## Repository Layout

The repository is a single Python package workspace with multiple app entry points and shared packages, all wired through the root `pyproject.toml`.

Top-level directories with active implementation value:

- `apps/` contains runnable services.
- `packages/` contains reusable code by boundary.
- `migrations/` contains Alembic environment and schema history.
- `tests/` contains unit and integration coverage.
- `scripts/` contains developer, runtime, and operational shell/Python helpers.
- `docs/` contains product, planning, contract, and runbook documentation.
- `.planning/codebase/` is for generated repository analysis artifacts like this one.

## App Directories

### `apps/api`

Purpose: internal HTTP API for health, debug/admin operations, workflow triggers, replay controls, and study ingest.

Key files:

- `apps/api/src/helm_api/main.py` creates the FastAPI app and mounts routers.
- `apps/api/src/helm_api/config.py` defines API settings from shared runtime config.
- `apps/api/src/helm_api/dependencies.py` provides DB session dependency wiring.
- `apps/api/src/helm_api/routers/` groups endpoints by workflow or control domain.
- `apps/api/src/helm_api/services/` contains thin application-service functions used by routers.
- `apps/api/src/helm_api/schemas.py` defines response/request models.

Observed pattern: routers are thin; service modules are also fairly thin and often proxy directly into repositories or agent helpers.

### `apps/worker`

Purpose: background scheduler and job executor.

Key files:

- `apps/worker/src/helm_worker/main.py` runs the poll loop and wraps jobs with run tracking.
- `apps/worker/src/helm_worker/config.py` defines worker-specific settings.
- `apps/worker/src/helm_worker/jobs/registry.py` is the central job registry.
- `apps/worker/src/helm_worker/jobs/email_triage.py` handles Gmail pull + triage.
- `apps/worker/src/helm_worker/jobs/digest.py` builds periodic digests.
- `apps/worker/src/helm_worker/jobs/study.py` handles study-related background work.
- `apps/worker/src/helm_worker/jobs/replay.py` handles failed-run replay queue processing.
- `apps/worker/src/helm_worker/jobs/scheduled_thread_tasks.py` resurfaces due thread tasks.
- `apps/worker/src/helm_worker/jobs/control.py` reads paused-job state.

Observed pattern: jobs are plain functions and the worker is intentionally simple.

### `apps/telegram-bot`

Purpose: Telegram-first V1 user interface.

Key files:

- `apps/telegram-bot/src/helm_telegram_bot/main.py` boots the Telegram application and registers commands.
- `apps/telegram-bot/src/helm_telegram_bot/config.py` reads Telegram config.
- `apps/telegram-bot/src/helm_telegram_bot/guards.py` restricts access to the allowed user.
- `apps/telegram-bot/src/helm_telegram_bot/commands/` contains one command module per Telegram command.
- `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py` bridges command handlers to email-agent operations.
- `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` formats and delivers digest output.

Observed pattern: this app is command-oriented and intentionally avoids broad UI abstractions.

## Shared Package Directories

### `packages/storage`

Purpose: persistence layer and the main cross-service integration boundary.

Key files:

- `packages/storage/src/helm_storage/db.py` defines engine, base, and session factory.
- `packages/storage/src/helm_storage/models.py` defines ORM tables.
- `packages/storage/src/helm_storage/repositories/` contains one repository module per aggregate or operational concern.
- `packages/storage/src/helm_storage/repositories/contracts.py` defines creation/update payload objects shared across repositories.

Repository modules map closely to tables and workflows, including:

- `action_items.py`
- `action_proposals.py`
- `agent_runs.py`
- `digest_items.py`
- `draft_replies.py`
- `draft_transition_audits.py`
- `email_agent_config.py`
- `email_drafts.py`
- `email_messages.py`
- `email_threads.py`
- `job_controls.py`
- `opportunities.py`
- `replay_queue.py`
- `scheduled_thread_tasks.py`
- `study_ingest.py`

### `packages/agents`

Purpose: business logic for workflow-specific behavior.

Internal split:

- `packages/agents/src/email_agent/` is the richest subpackage. It contains the email runtime protocol, Helm adapter, triage workflow, operator flows, query helpers, scheduling logic, and typed records.
- `packages/agents/src/helm_agents/digest_agent.py` builds ranked digest output from persisted artifacts.
- `packages/agents/src/helm_agents/study_agent.py` extracts study summaries, tasks, and gaps from raw text.

Observed pattern: `email_agent` is structured like a reusable package; `helm_agents/*` is simpler and more direct.

### `packages/connectors`

Purpose: external system ingress and normalization.

Key files:

- `packages/connectors/src/helm_connectors/gmail.py` normalizes Gmail payloads, manages auth, and can fetch message details from Gmail.

This package is narrow today and mostly email-specific.

### `packages/domain`

Purpose: shared business primitives without storage/network concerns.

Key files:

- `packages/domain/src/helm_domain/models.py`

Observed pattern: this boundary exists but is still very light compared with the storage and agent layers.

### `packages/llm`

Purpose: model invocation and prompt-contract boundary.

Key files:

- `packages/llm/src/helm_llm/client.py`

Observed pattern: the package exists, but only a minimal wrapper is present and most workflow logic is not yet centered here.

### `packages/observability`

Purpose: logging and persisted run tracing.

Key files:

- `packages/observability/src/helm_observability/logging.py`
- `packages/observability/src/helm_observability/agent_runs.py`

This package is structurally important because both API-triggered and worker-triggered execution paths use it.

### `packages/orchestration`

Purpose: intended home for LangGraph/state transitions.

Key files:

- `packages/orchestration/src/helm_orchestration/__init__.py`

Observed pattern: placeholder boundary at the moment. Real orchestration code currently lives elsewhere.

### `packages/runtime`

Purpose: shared runtime configuration and operational utility code.

Key files:

- `packages/runtime/src/helm_runtime/config.py`
- `packages/runtime/src/helm_runtime/pr_linear_reconcile.py`

This package provides common settings classes used by all app entry points.

## Supporting Directories

### `migrations`

Purpose: Alembic setup and schema evolution.

Key files:

- `migrations/env.py`
- `migrations/script.py.mako`
- `migrations/versions/20260308_0001_v1_baseline.py`
- `migrations/versions/20260309_0002_linkedin_thread_external_id.py`
- `migrations/versions/20260309_0003_replay_queue.py`
- `migrations/versions/20260309_0004_job_controls.py`
- `migrations/versions/20260309_0005_draft_transition_audits.py`
- `migrations/versions/20260310_0006_remove_linkedin_artifacts.py`

Observed pattern: migrations show an active schema transition history, including removal of a LinkedIn-related artifact line.

### `tests`

Purpose: unit and integration verification.

Structure:

- `tests/integration/` covers route/scaffold behavior.
- `tests/unit/` covers agents, repositories, Telegram services, worker jobs, replay logic, and health/status paths.
- `tests/fixtures/README.md` documents test fixtures.

Representative files:

- `tests/unit/test_storage_repositories.py`
- `tests/unit/test_worker_digest_job.py`
- `tests/unit/test_telegram_command_service.py`
- `tests/unit/test_replay_queue.py`
- `tests/integration/test_routes.py`

### `scripts`

Purpose: local development, health checks, runtime boot, and operational helpers.

Representative files:

- `scripts/run-api.sh`
- `scripts/run-worker.sh`
- `scripts/run-telegram-bot.sh`
- `scripts/migrate.sh`
- `scripts/lint.sh`
- `scripts/test.sh`
- `scripts/smoke.sh`
- `scripts/compose-api-health-smoke.sh`
- `scripts/bootstrap.sh`
- `scripts/doctor.sh`
- `scripts/install-night-runner-cron.sh`
- `scripts/night-runner.sh`
- `scripts/check-gmail-auth.py`
- `scripts/linear_intake.py`
- `scripts/pr_linear_reconcile.py`

## Packaging And Runtime Files

- `pyproject.toml` is the single packaging definition and includes all app/package source roots in setuptools discovery.
- `Dockerfile` builds one Python image for all services.
- `docker-compose.yml` defines `postgres`, `migrate`, `api`, `worker`, and `telegram-bot`.
- `.env.example` documents required runtime configuration for app, database, OpenAI, Telegram, Gmail, scheduling, and Linear integration.

## Practical Navigation Map

If you need to trace behavior quickly:

- API request path: `apps/api/src/helm_api/routers/` -> `apps/api/src/helm_api/services/` -> `packages/storage` or `packages/agents`
- Worker job path: `apps/worker/src/helm_worker/jobs/` -> `packages/connectors` or `packages/agents` -> `packages/storage`
- Telegram command path: `apps/telegram-bot/src/helm_telegram_bot/commands/` -> `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py` -> `packages/agents/src/email_agent`
- Persistence path: `packages/storage/src/helm_storage/repositories/` -> `packages/storage/src/helm_storage/models.py`
- Run tracking path: `packages/observability/src/helm_observability/agent_runs.py` -> `packages/storage/src/helm_storage/repositories/agent_runs.py`

## Structural Assessment

- The top-level layout is clear and matches the collaboration boundaries documented in `AGENTS.md`.
- The deepest directory density is in `packages/storage` and `packages/agents/src/email_agent`, which are the real center of gravity.
- `packages/orchestration` and `packages/domain` are present as future-facing boundaries, but the current implementation weight sits elsewhere.
- The repository is easy to navigate by runtime surface area because each app has a narrow source tree and explicit entry point.
