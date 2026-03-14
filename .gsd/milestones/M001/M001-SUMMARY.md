---
id: M001
provides:
  - Durable workflow kernel with typed persistence for runs, steps, artifacts, and transition history
  - Kernel-owned specialist dispatch with TaskAgent and CalendarAgent invocation records
  - Approval checkpoints with revision-driven proposal versioning and resume semantics
  - Adapter-gated sync execution with idempotency, retry, replay, and recovery classification
  - Representative weekly scheduling workflow exercising the full kernel lifecycle
  - Shared API and Telegram operator surfaces for workflow status, approval, replay, and lineage inspection
key_decisions:
  - Dedicated workflow_* tables rather than extending legacy email or observability tables
  - Specialist invocations persisted in a relational table with artifact linkage, not hidden in payloads
  - Approval checkpoints in a dedicated table linked to proposal artifacts with version-targeted decisions
  - Sync identity anchored to proposal/version/target/kind/planned_item_key with relational uniqueness
  - Replay creates new sync lineage generations preserving prior history
  - Recovery classification lives on durable sync rows, not inferred from error text
  - Shared status projection consumed by both API and Telegram to prevent surface divergence
patterns_established:
  - Kernel-owned step advancement with durable failure, validation blocking, and restart-safe resume
  - Typed Pydantic schemas for all workflow payloads with validator registry
  - Specialist registration keyed by (workflow_type, step_name) to avoid handler collisions
  - Approval-blocked state using explicit blocked_reason instead of generic status inference
  - Reconciliation-first retry where uncertain outcomes must prove provider state before re-executing
  - Shared read-model services consumed identically by API routes and Telegram commands
  - Auto-persisted final summary artifacts with durable approval and sync lineage
observability_surfaces:
  - API workflow run routes for create, list, detail, retry, terminate, approve, reject, revision, replay
  - Telegram commands for workflow start, summary, needs-action, approve, reject, revision, replay
  - Shared workflow status projection with paused_state, available_actions, safe_next_actions, effect summaries, and completion summaries
  - Durable workflow_events table for append-only transition history
  - Recovery classification and replay lineage queryable from workflow_sync_records
requirement_outcomes:
  - id: REQ-DURABLE-PERSISTENCE
    from_status: active
    to_status: validated
    proof: S01 established workflow_runs/steps/artifacts/events tables with 6 migrations, verified by test_workflow_repositories.py (schema creation, lineage, blocked validation, execution failure, resume-safe reads)
  - id: REQ-SPECIALIST-DISPATCH
    from_status: active
    to_status: validated
    proof: S02/T01 added workflow_specialist_invocations table with typed TaskAgent/CalendarAgent dispatch, verified by specialist invocation persistence and execution tests
  - id: REQ-APPROVAL-CHECKPOINTS
    from_status: active
    to_status: validated
    proof: S02/T02-T03 added workflow_approval_checkpoints table with approve/reject/revision decisions and version-targeted proposal lineage, verified by approval and revision orchestration tests
  - id: REQ-ADAPTER-SYNC
    from_status: active
    to_status: validated
    proof: S03 added workflow_sync_records with 3 migrations, adapter protocols, idempotent execution, replay lineage, recovery classification, and shared status projection, verified by 40+ sync-specific tests
  - id: REQ-REPRESENTATIVE-WORKFLOW
    from_status: active
    to_status: validated
    proof: S04 wired end-to-end weekly scheduling from shared request contract through normalization, proposal, approval, sync, completion, and replay-aware recovery, verified by representative integration and unit tests
  - id: REQ-OPERATOR-SURFACES
    from_status: active
    to_status: validated
    proof: S01/T03 and S02-S04 built shared API/Telegram operator tooling for all workflow lifecycle actions, verified by test_workflow_status_routes.py and test_telegram_commands.py
duration: ~6 hours across 14 tasks in 4 slices
verification_result: passed
completed_at: 2026-03-13
---

# M001: Helm Orchestration Kernel v1

**Durable workflow engine with typed specialist dispatch, approval-gated side effects, restart-safe resume, replay-aware recovery, and shared operator surfaces across API and Telegram — validated end to end by a representative weekly scheduling workflow.**

## What Happened

M001 shipped the orchestration kernel for Helm in four slices building on each other sequentially.

**S01 (Durable Workflow Foundation)** established the persistence vocabulary: `workflow_runs`, `workflow_steps`, `workflow_artifacts`, and `workflow_events` tables with typed SQLAlchemy models and Pydantic schemas. It also built the orchestration state machine (validation gating, failure persistence, retry/terminate actions, restart-safe resume) and exposed everything through a shared read-model service consumed by FastAPI API routes and Telegram bot commands.

**S02 (Specialist Dispatch And Approval Semantics)** turned the state machine into a typed specialist execution kernel. It added a `workflow_specialist_invocations` table, typed TaskAgent and CalendarAgent dispatch contracts, and a `workflow_approval_checkpoints` table for durable approval gating. The approval story included revision-linked proposal versioning, supersession lineage, and version-targeted operator decisions across API and Telegram.

**S03 (Adapter Writes And Recovery Guarantees)** was the largest slice (5 tasks) and built the complete outbound write infrastructure. It added `workflow_sync_records` with deterministic identity, adapter protocols with normalized request/outcome/reconciliation envelopes, idempotent execution with reconciliation-first recovery, explicit recovery classification (recoverable, terminal, retry, replay, terminate-after-partial-success), replay lineage generations, a shared status projection reading durable sync facts, and explicit replay entry points via API, worker, and Telegram.

**S04 (Representative Scheduling Workflow)** replaced demo stubs with a real weekly scheduling flow exercising the full kernel. It implemented a shared request contract, deterministic task normalization, rich schedule proposals with constraints and carry-forward tracking, auto-persisted final summary artifacts with approval and sync lineage, compact completion summaries, and replay-aware recovery overrides.

## Cross-Slice Verification

**Criterion 1: Durable workflow runs, steps, artifacts, and lineage are persisted and inspectable.**
✅ Verified. S01 established 4 core tables with typed repositories. `test_workflow_repositories.py` covers schema creation, artifact lineage/versioning, blocked validation, execution failure, and resume-safe reads. S04 proves end-to-end lineage from request through final summary.

**Criterion 2: Typed specialist dispatch with durable invocation records.**
✅ Verified. S02/T01 added `workflow_specialist_invocations` table with input/output artifact linkage and execution status. `test_workflow_orchestration_service.py` covers task-to-calendar specialist execution, warnings, validation blocking, and restart-safe resumption with semantic handler keys.

**Criterion 3: Approval checkpoints with revision-driven proposal versioning and kernel-owned resume semantics.**
✅ Verified. S02/T02 added `workflow_approval_checkpoints` table. S02/T03 added revision-linked proposal versions with supersession lineage. Tests cover approval pause, approve-to-resume, reject-to-close, revision-to-regenerate, multi-revision correctness, and version-targeted operator decisions.

**Criterion 4: Adapter-gated sync execution with idempotency, retry, replay, and recovery classification.**
✅ Verified. S03 added `workflow_sync_records` with 3 supporting migrations. Tests cover deterministic task-before-calendar ordering, retryable stop on uncertain outcomes, reconciliation-first resume, restart-safe retry, replay vs retry lineage distinction, terminal failure classification, and terminate-after-partial-success preservation.

**Criterion 5: Representative weekly scheduling workflow from request through approved writes and replay-aware final lineage.**
✅ Verified. S04 wired the full flow: shared request parsing → task normalization → schedule proposal → approval checkpoint → revision cycle → approved sync execution → final summary artifact → completion projection → replay-aware recovery override. All 82 M001-specific tests pass (341 total passed, 2 pre-existing legacy email replay test failures unrelated to M001).

## Requirement Changes

- REQ-DURABLE-PERSISTENCE: active → validated — 4 core tables, 6 migrations, repository tests proving durability, lineage, and restart-safe reads.
- REQ-SPECIALIST-DISPATCH: active → validated — dedicated invocation table, typed TaskAgent/CalendarAgent contracts, specialist execution tests.
- REQ-APPROVAL-CHECKPOINTS: active → validated — checkpoint table, approve/reject/revision decisions, version-targeted proposal lineage, multi-revision tests.
- REQ-ADAPTER-SYNC: active → validated — sync records with relational identity, adapter protocols, idempotent execution, replay lineage, recovery classification, 40+ sync-specific tests.
- REQ-REPRESENTATIVE-WORKFLOW: active → validated — end-to-end weekly scheduling flow verified across create, revision, approval, sync, completion, and replay recovery.
- REQ-OPERATOR-SURFACES: active → validated — shared API/Telegram surfaces for all workflow lifecycle actions with status route and command tests.

## Forward Intelligence

### What the next milestone should know
- The kernel contract is proven but only exercised by one workflow type (`weekly_scheduling`). The next workflow type will reveal whether the specialist registration and step-handler patterns generalize cleanly.
- Adapter stubs in `packages/connectors` return success deterministically. Real API integrations will need reconciliation behavior that the kernel already supports but hasn't been tested against real provider failures.
- The 2 failing tests in `test_replay_queue.py` are legacy email replay tests broken by the v1.0 merge dropping `build_email_agent_runtime` from the replay worker module. They need fixing when email replay is revisited.

### What's fragile
- Proposal generation is deterministic but naive — it doesn't call LLM or real scheduling logic. Real specialist behavior will need the same durable invocation contract but much richer execution.
- The shared status projection in `workflow_status_service.py` accumulates complexity as it serves effect summaries, sync counts, recovery classification, completion summaries, and replay lineage. Additional workflow types will stress this surface.
- Migration chain (0007–0012) is linear and tested against SQLite. Postgres-specific behaviors (e.g., constraint enforcement, transaction isolation) haven't been validated in CI.

### Authoritative diagnostics
- `test_workflow_orchestration_service.py` is the most comprehensive test file — it covers the full kernel lifecycle and is the first place to look when kernel behavior changes.
- `apps/api/src/helm_api/services/workflow_status_service.py` is the shared projection truth — if API and Telegram disagree, this file is the source of truth.
- `docs/runbooks/workflow-runs.md` has manual verification steps for all major workflow operations.

### What assumptions changed
- Originally assumed specialist dispatch would be simple function calls — it became a full invocation-tracking subsystem with input/output artifact linkage.
- Originally assumed replay and retry would share mechanics — they were separated into distinct lineage generation systems because replay needed to preserve prior execution history.
- The merge into main revealed that the legacy email replay worker interface had diverged; the kernel's replay service is now the authoritative replay path.

## Files Created/Modified

- `migrations/versions/20260313_0007_workflow_foundation.py` — Core workflow tables (runs, steps, artifacts, events).
- `migrations/versions/20260313_0008_specialist_dispatch.py` — Specialist invocation table.
- `migrations/versions/20260313_0009_approval_checkpoints.py` — Approval checkpoint table and resume metadata.
- `migrations/versions/20260313_0010_workflow_sync_records.py` — Outbound sync record table.
- `migrations/versions/20260313_0011_workflow_sync_execution.py` — Sync attempt metadata columns.
- `migrations/versions/20260313_0012_workflow_recovery_lineage.py` — Recovery and replay lineage columns.
- `packages/storage/src/helm_storage/models.py` — All workflow ORM models.
- `packages/storage/src/helm_storage/repositories/` — Workflow repository contracts and implementations (runs, steps, artifacts, events, specialist invocations, approval checkpoints, sync records, replay queue).
- `packages/orchestration/src/helm_orchestration/schemas.py` — Typed workflow, specialist, approval, sync, and recovery schemas.
- `packages/orchestration/src/helm_orchestration/contracts.py` — Specialist dispatch and adapter protocol contracts.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` — Core orchestration service (run creation, step transitions, specialist dispatch, approval handling, sync execution, completion).
- `packages/orchestration/src/helm_orchestration/resume_service.py` — Restart-safe resume and specialist handler resolution.
- `packages/orchestration/src/helm_orchestration/validators.py` — Validator registry and normalized-task validation.
- `apps/api/src/helm_api/services/workflow_status_service.py` — Shared workflow status projection.
- `apps/api/src/helm_api/services/replay_service.py` — Shared replay execution helpers.
- `apps/api/src/helm_api/routers/workflow_runs.py` — Workflow run API routes.
- `apps/api/src/helm_api/routers/replay.py` — Workflow replay API route.
- `apps/api/src/helm_api/schemas.py` — API request/response schemas.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — Worker workflow polling and specialist wiring.
- `apps/worker/src/helm_worker/jobs/replay.py` — Worker replay queue handoff.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` — Telegram workflow commands.
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py` — Telegram approval commands.
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — Telegram workflow status wrapper.
- `packages/connectors/src/helm_connectors/task_system.py` — Task adapter stub.
- `packages/connectors/src/helm_connectors/calendar_system.py` — Calendar adapter stub.
- `docs/runbooks/workflow-runs.md` — Manual verification runbook.
