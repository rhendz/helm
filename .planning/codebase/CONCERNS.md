# Codebase Concerns

## Summary

The main concerns are incomplete execution paths, mixed old/new data models, and several fail-open behaviors around storage and operations. The repository is usable as a scaffold, but parts of the runtime still fall short of the V1 spec in `docs/internal/helm-v1.md`, especially around durable workflow execution, approval handling, and operational safety.

## Highest-Priority Concerns

### 1. Replay is exposed but not implemented

- Evidence: `apps/api/src/helm_api/routers/replay.py` exposes enqueue and reprocess endpoints, and `apps/worker/src/helm_worker/jobs/replay.py` consumes replay items, but `_execute_replay` raises `NotImplementedError`.
- Why it matters: operators can create replay work that is guaranteed to fail. This adds noise to `agent_runs`, leaves dead-letter style items in `replay_queue`, and creates a misleading recovery story.
- Suggested action: either finish replay dispatch by source type or disable the replay API and worker job until a real handler exists.

### 2. Draft handling is split across two schemas

- Evidence: the digest path still reads legacy `DraftReplyORM` through `packages/storage/src/helm_storage/repositories/draft_replies.py` and `packages/agents/src/helm_agents/digest_agent.py`, while email triage, Telegram approval, and API draft views use `EmailDraftORM` via `packages/storage/src/helm_storage/repositories/email_drafts.py` and `packages/agents/src/email_agent/adapters/helm_runtime.py`.
- Why it matters: the system now has two draft concepts with different status fields (`status` vs `approval_status`). Digest ranking, stale-draft detection, and approval flows can drift because they do not read from the same source of truth.
- Suggested action: pick one draft model for V1, migrate callers, and remove the unused path.

### 3. Workflow persistence is not transactional

- Evidence: `packages/agents/src/email_agent/adapters/helm_runtime.py` opens a new `SessionLocal` scope per runtime method. `packages/agents/src/email_agent/triage.py` performs run start, thread upsert, message upsert, proposal creation, draft creation, digest creation, and run completion as separate commits.
- Why it matters: partial writes are easy to create. A failure after the message is stored but before downstream artifacts are written leaves the thread in a partially updated state with no rollback boundary.
- Suggested action: introduce a unit-of-work or explicit workflow transaction boundary for each triage run.

### 4. Operational controls fail open when storage is unavailable

- Evidence: `packages/observability/src/helm_observability/agent_runs.py` silently drops run tracking if the database is down. `apps/worker/src/helm_worker/jobs/control.py` returns `False` on query failure, so paused jobs resume automatically. `apps/api/src/helm_api/services/job_control_service.py` returns the requested pause state even when persistence fails.
- Why it matters: on a DB issue the system can continue executing jobs without auditability, while the control plane reports a state that may not exist in storage.
- Suggested action: make control and run-tracking failures visible and fail closed for pause checks.

### 5. Gmail ingestion has no durable cursor despite schema support

- Evidence: `packages/connectors/src/helm_connectors/gmail.py` lists the latest 25 messages every poll and does not persist Gmail history state. `packages/storage/src/helm_storage/models.py` and `packages/storage/src/helm_storage/repositories/email_agent_config.py` include `last_history_cursor`, but the value is unused.
- Why it matters: the worker repeatedly scans recent mail instead of advancing from a durable checkpoint. Upsert logic limits duplicate inserts, but polling cost and repeated processing attempts remain operational debt.
- Suggested action: implement Gmail history cursor tracking and make ingestion incremental.

## Architecture And Boundary Concerns

### 6. Domain and orchestration boundaries are mostly placeholders

- Evidence: `packages/domain/src/helm_domain/models.py` contains one small dataclass and a TODO. `packages/orchestration/README.md` defines intended boundaries, but there is no matching orchestration implementation under `packages/orchestration/src/helm_orchestration/`.
- Why it matters: app and service layers are already reaching directly into `email_agent` and storage code, which weakens the repo boundary plan described in `AGENTS.md`.
- Suggested action: either collapse the unused package boundaries or move real orchestration/domain contracts into those packages before more features land.

### 7. App layer depends directly on agent internals

- Evidence: `apps/api/src/helm_api/services/email_service.py`, `apps/api/src/helm_api/services/draft_service.py`, and `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py` import `email_agent.adapters`, `email_agent.operator`, and `email_agent.query` directly.
- Why it matters: transport layers are coupled to package-internal behavior instead of stable package APIs. Refactors inside `packages/agents` will ripple across API and bot code.
- Suggested action: put explicit application-facing facades in package boundaries and route app code through them.

### 8. API control endpoints have no authentication layer

- Evidence: `apps/api/src/helm_api/main.py` registers routers directly, and routes in `apps/api/src/helm_api/routers/job_controls.py`, `apps/api/src/helm_api/routers/replay.py`, and `apps/api/src/helm_api/routers/workflows.py` have no dependency or guard for internal-only access.
- Why it matters: the repo is intentionally single-user and internal, but these endpoints pause jobs, enqueue replay work, and trigger workflow runs. If the API is exposed beyond localhost, there is no protection.
- Suggested action: add an internal auth dependency or explicitly constrain deployment/network exposure in code and docs.

## Feature Completeness Concerns

### 9. Study workflow is only partially implemented

- Evidence: `apps/worker/src/helm_worker/jobs/study.py` is a TODO stub, `apps/telegram-bot/src/helm_telegram_bot/commands/study.py` is also a TODO stub, and `packages/agents/src/helm_agents/study_agent.py` uses heuristic extraction only.
- Why it matters: the V1 spec expects study execution and weakness tracking to be a first-class workflow, but the current implementation only covers manual ingest plus lightweight parsing.
- Suggested action: decide whether study is in current V1 scope. If yes, complete the worker/bot loop; if not, trim the exposed surface.

### 10. Approval flow stops at status mutation

- Evidence: `packages/agents/src/email_agent/operator.py` changes draft approval state and explicitly returns "Not sent yet." There is no send path tied to approval in `apps/telegram-bot` or `apps/api`.
- Why it matters: this is safe relative to the approval requirement in `docs/internal/helm-v1.md`, but it means the workflow is incomplete. Approved drafts accumulate without a durable outbound execution step.
- Suggested action: define the post-approval send workflow and its audit trail, or relabel approval as "mark ready" until sending exists.

## Testing And Reliability Concerns

### 11. Integration coverage is still mostly scaffold-level

- Evidence: `tests/integration/test_scaffold.py` is a placeholder. `tests/integration/test_routes.py` mostly verifies route availability and permissive response shapes rather than end-to-end persistence and workflow outcomes.
- Why it matters: the biggest risks in this codebase are cross-boundary issues, but the current tests mainly exercise isolated units and happy-path route wiring.
- Suggested action: add end-to-end tests for email triage, digest generation, job pause behavior, and replay queue semantics against a real test database.

### 12. Several services return success-shaped responses on persistence failure

- Evidence: `apps/api/src/helm_api/services/study_service.py` returns `"status": "accepted"` even when `persisted` is `False`. `apps/api/src/helm_api/services/job_control_service.py` returns the requested pause value after `SQLAlchemyError`.
- Why it matters: clients can treat a request as completed when the system actually failed to store the state change. That makes debugging and operator trust much harder.
- Suggested action: separate accepted-vs-persisted semantics more clearly, and surface storage failures as explicit errors for control-plane operations.

## Watchlist

- `packages/storage/src/helm_storage/db.py` uses module-level engine/session construction from environment variables, which makes test isolation and alternate runtime wiring harder over time.
- `migrations/versions/20260308_0001_v1_baseline.py` shows the repository has already had one schema pivot, including removed LinkedIn tables and older email tables. More churn is likely unless the V1 data model is stabilized soon.
- `tests/fixtures/README.md` still calls out missing anonymized fixtures, which will slow realistic regression testing for email parsing and triage behavior.
