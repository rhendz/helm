# Architecture

## Intent And Current Shape

`helm` is a monorepo-style Python application for a personal AI assistant. The product contract in `docs/internal/helm-v1.md` is Telegram-first, DB-first, artifact-driven, and human-supervised for outbound actions.

The runtime is split into three app entry points:

- `apps/api/src/helm_api/main.py` boots a FastAPI service for health, admin, replay, artifact inspection, and study ingestion endpoints.
- `apps/worker/src/helm_worker/main.py` runs a polling worker that executes registered background jobs and wraps them in run tracking.
- `apps/telegram-bot/src/helm_telegram_bot/main.py` runs a Telegram bot using long polling and exposes approval/status commands.

Shared behavior is implemented in `packages/*`, with `packages/storage` currently acting as the main durable integration point across the system.

## High-Level Component Model

### App Layer

- `apps/api` is an internal control plane. It exposes read/write endpoints and calls service functions that usually talk directly to repositories or to `email_agent`.
- `apps/worker` is the scheduler/executor. It loops forever, checks pause state, and runs jobs from `apps/worker/src/helm_worker/jobs/registry.py`.
- `apps/telegram-bot` is the primary user interface for V1. It handles `/digest`, `/actions`, `/drafts`, `/study`, `/approve`, and `/snooze`.

### Package Layer

- `packages/storage/src/helm_storage` owns SQLAlchemy engine setup, ORM models, and repository classes.
- `packages/agents/src/email_agent` contains the most complete workflow implementation: triage logic, operator flows, query helpers, scheduling behavior, and a runtime protocol.
- `packages/agents/src/helm_agents` contains digest and study logic, both implemented as direct functions rather than graph-based orchestrations.
- `packages/connectors/src/helm_connectors/gmail.py` normalizes Gmail payloads and can pull messages from the Gmail API when configured.
- `packages/llm/src/helm_llm/client.py` is a thin OpenAI wrapper; it is not yet the central prompt-contract layer described in the repo boundary docs.
- `packages/observability/src/helm_observability` owns structured logging setup and persisted agent-run lifecycle recording.
- `packages/runtime/src/helm_runtime/config.py` provides shared settings classes used by all app entry points.
- `packages/domain/src/helm_domain/models.py` is minimal and currently underused relative to the database model layer.
- `packages/orchestration/src/helm_orchestration/__init__.py` is effectively a placeholder. LangGraph is used directly inside `packages/agents/src/email_agent/triage.py` instead of through this package.

## Primary Runtime Flows

### 1. Email Triage Flow

1. `apps/worker/src/helm_worker/jobs/email_triage.py` pulls normalized Gmail messages through `packages/connectors/src/helm_connectors/gmail.py`.
2. The job calls `packages/agents/src/email_agent/triage.py`.
3. `run_email_triage_workflow()` creates an agent run, upserts the inbound message, runs a small LangGraph state machine, and persists artifacts.
4. Persistence is done through the runtime adapter in `packages/agents/src/email_agent/adapters/helm_runtime.py`, which maps protocol operations onto SQLAlchemy repositories in `packages/storage/src/helm_storage/repositories`.
5. Resulting durable artifacts include updates to `email_threads`, `email_messages`, `action_proposals`, `email_drafts`, `digest_items`, and `agent_runs` via ORM definitions in `packages/storage/src/helm_storage/models.py`.

This is the clearest example of the intended DB-first architecture.

### 2. Daily Digest Flow

1. The worker runs `apps/worker/src/helm_worker/jobs/digest.py`, or the API triggers digest generation through `apps/api/src/helm_api/routers/workflows.py`.
2. Both paths call `packages/agents/src/helm_agents/digest_agent.py`.
3. The digest agent reads action items, digest items, and draft replies directly from storage repositories.
4. The Telegram delivery path uses `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` to present the text to the user.

This flow is storage-centric but bypasses `packages/orchestration` and mostly bypasses `packages/domain`.

### 3. Telegram Approval Flow

1. `apps/telegram-bot/src/helm_telegram_bot/commands/*.py` routes commands into `TelegramCommandService`.
2. `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py` calls `email_agent.operator`.
3. `packages/agents/src/email_agent/operator.py` reads and updates draft approval state using the Helm runtime adapter.
4. Approval changes are persisted in `packages/storage`; no send step is automatically triggered.

This aligns with the V1 requirement that meaningful outbound actions remain human-supervised.

### 4. Study Ingest Flow

1. `apps/api/src/helm_api/routers/study.py` accepts manual study notes.
2. `apps/api/src/helm_api/services/study_service.py` calls `packages/agents/src/helm_agents/study_agent.py`.
3. The study agent performs heuristic extraction and stores sessions, knowledge gaps, and learning tasks through `packages/storage/src/helm_storage/repositories/study_ingest.py`.

This is pragmatic and simple, but still heuristic-first rather than LLM-contract-first.

### 5. Replay / Control / Status Flow

- Job pause/resume uses `apps/api/src/helm_api/services/job_control_service.py` with `packages/storage/src/helm_storage/repositories/job_controls.py`.
- Replay enqueue/reprocess uses `apps/api/src/helm_api/services/replay_service.py` and worker job `apps/worker/src/helm_worker/jobs/replay.py`.
- Run tracking is shared through `packages/observability/src/helm_observability/agent_runs.py`.

These flows add a lightweight internal operations plane around the core agent pipelines.

## Data Ownership

The central architectural fact is that Postgres is the system of record.

- Connection/session bootstrapping lives in `packages/storage/src/helm_storage/db.py`.
- Schema lives in `packages/storage/src/helm_storage/models.py`.
- Migrations live in `migrations/versions/`.

The storage model is broader than the current domain model package and captures most durable workflow state directly:

- email artifacts: `EmailThreadORM`, `EmailMessageORM`, `ActionProposalORM`, `EmailDraftORM`, `ScheduledThreadTaskORM`, `EmailAgentConfigORM`
- user-facing artifacts: `ActionItemORM`, `DraftReplyORM`, `DigestItemORM`, `OpportunityORM`
- study artifacts: `StudySessionORM`, `KnowledgeGapORM`, `LearningTaskORM`
- ops artifacts: `AgentRunORM`

This means architectural coupling is currently repository/ORM-centric, not domain-model-centric.

## Dependency Direction

The dominant dependency pattern is:

`apps/*` -> `packages/agents` or direct repository/services -> `packages/storage`

Supporting packages sit beside that path:

- `packages/connectors` feeds normalized external data into agents.
- `packages/observability` wraps execution and logging.
- `packages/runtime` provides config.
- `packages/llm` is available but not consistently used by the current agents.

The cleanest abstraction in the codebase is the `EmailAgentRuntime` protocol in `packages/agents/src/email_agent/runtime.py`, which isolates `email_agent` logic from Helm-specific persistence details. The adapter in `packages/agents/src/email_agent/adapters/helm_runtime.py` is the bridge.

## Architectural Strengths

- The repo follows the intended top-level split from `AGENTS.md`, so parallel work by boundary is practical.
- Durable state is explicit and queryable; most important workflows persist artifacts rather than relying on prompt state.
- The email workflow has a clear runtime protocol and adapter boundary, which is the strongest reusable architectural pattern in the codebase.
- Operational controls exist early: health, replay, job pause/resume, and failed-run inspection are already exposed.
- Telegram remains the actual primary user surface, which matches the V1 spec.

## Architectural Gaps And Tensions

### Intended Boundaries vs Actual Coupling

- `packages/orchestration` is mostly empty, while workflow orchestration sits inside `packages/agents/src/email_agent/triage.py`.
- `packages/domain` is much thinner than the ORM layer, so business concepts live primarily in SQLAlchemy models and dict payloads.
- `apps/api/src/helm_api/services/*.py` often couples directly to storage or to `email_agent` helpers rather than to a dedicated application-service layer.
- `packages/llm` is not yet the authoritative prompt-contract boundary promised in `packages/llm/README.md`.

### Parallel Legacy Artifact Model

There are two overlapping artifact families in `packages/storage/src/helm_storage/models.py`:

- newer email-specific artifacts: `EmailThreadORM`, `ActionProposalORM`, `EmailDraftORM`
- older generic artifacts: `ActionItemORM`, `DraftReplyORM`, `DigestItemORM`, `OpportunityORM`

The current system uses both. That is workable, but it means architecture documentation should treat the repo as partially transitioned rather than fully unified on one artifact vocabulary.

### Execution Model Simplicity

- The worker is a polling loop in `apps/worker/src/helm_worker/main.py`, not a queue-based executor.
- Telegram runs polling rather than webhook delivery.
- Several jobs and services instantiate storage/session dependencies directly instead of routing through more explicit composition roots.

This keeps the code simple, but also means cross-cutting behavior is distributed rather than centrally composed.

## Practical Boundary Map

- Best-isolated boundary today: `packages/storage`
- Best-defined workflow boundary today: `packages/agents/src/email_agent`
- Most user-visible boundary today: `apps/telegram-bot`
- Thinnest intended-but-not-yet-realized boundary: `packages/orchestration`
- Most structurally important cross-cutting package: `packages/observability`

## Recommendations For Future Work

- Move graph/state-machine ownership behind `packages/orchestration` and keep `packages/agents` focused on business decisions and artifact generation.
- Expand `packages/domain` with stable value objects/enums used by API schemas, agent logic, and repositories so business rules stop living in dicts and ORM fields.
- Choose a single durable artifact vocabulary for drafts/actions/opportunities and retire parallel legacy tables only after callers converge.
- Introduce explicit application-service composition for API and worker jobs where direct repository access has spread across app code.
- Make `packages/llm` the single place for structured prompts, model selection, and response contracts before more LLM-backed agents are added.
