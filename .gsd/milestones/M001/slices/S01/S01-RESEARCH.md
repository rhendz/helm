# Phase 1 Research: Durable Workflow Foundation

## What Phase 1 Needs To Establish

Phase 1 should create the durable kernel contract that later specialist, approval, and adapter work can sit on without reworking persistence again. In this repo, that means introducing a workflow-native model alongside the existing email-specific tables, not trying to stretch `agent_runs` or the legacy artifact tables into the kernel contract.

The planner should optimize for four outcomes:

1. A workflow run can be created, resumed, and inspected from Postgres.
2. Step boundaries are durable and explicit enough that restart behavior is driven by stored state, not by in-memory LangGraph state.
3. Artifacts and validation results are first-class persisted records with lineage.
4. Operator-facing read paths can answer the triage question from the Phase 1 context: what run is this, what step is it on, what happened last, and does it need action now?

## Repo-Specific Constraints

- Postgres is already the source of truth. The codebase already relies on SQLAlchemy repositories and Alembic migrations in `packages/storage`.
- `packages/orchestration` is the intended home for workflow state transitions, but it is currently empty. Phase 1 should start making it real.
- The worker is a polling loop, not a queue system. Any Phase 1 design that assumes a broker or event bus will create extra infrastructure surface immediately.
- LangGraph is already present, but only inside `email_agent`. The planner should treat LangGraph as optional orchestration logic, not the durable state store.
- API and Telegram surfaces already exist and should read the new workflow records rather than inventing a second status model.

## Durable Vocabulary To Introduce

The planner should use a kernel-native vocabulary with explicit tables and enums, even if the first workflow is minimal.

Recommended durable objects:

- `workflow_runs`: one row per run, with workflow type, status, current step name, needs-action flag, last event summary, started/completed timestamps, and restart-safe identity.
- `workflow_steps`: one row per attempt of a named step within a run, with status, attempt number, started/completed timestamps, failure summary, retryability, and validation outcome summary.
- `workflow_artifacts`: versioned typed artifacts linked to run and optional producing step. This should hold raw request, normalized task artifact, validation report, and final summary artifacts for Phase 1.
- `workflow_artifact_links` or equivalent parent references: enough lineage to answer “artifact B came from validating artifact A” without reconstructing history from logs.
- `workflow_events` or durable transition history: append-only state changes for inspection and debugging.

The planner does not need full generic workflow-template infrastructure yet. A small fixed workflow type enum is enough if the schema shape stays reusable.

## Suggested Status Model

Keep statuses boring and explicit. The planner should avoid deriving meaning from many loosely defined strings.

Recommended run statuses:

- `pending`
- `running`
- `blocked`
- `failed`
- `completed`
- `terminated`

Recommended step statuses:

- `pending`
- `running`
- `succeeded`
- `validation_failed`
- `failed`
- `cancelled`

Recommended artifact lifecycle fields:

- artifact type
- schema version
- version number within run
- producer step
- supersedes artifact id nullable
- created at
- JSON payload

This supports the Phase 1 requirement that valid artifacts can carry warnings while invalid artifacts block execution durably.

## Temporal Versus Postgres-First Custom Runtime

This evaluation should be locked during planning because it changes how much of Phase 1 is persistence design versus platform integration.

### Option A: Temporal

Strengths for Helm:

- Strong built-in durability, retries, timers, and resume semantics.
- Long waits and human approval pauses fit Temporal naturally.
- Later phases around approval and recovery would be easier to express as workflow continuations rather than custom polling logic.

Costs for this repo and phase:

- It adds a second durable execution substrate next to the Postgres artifact model that Helm already treats as truth.
- Phase 1 would spend meaningful effort on Temporal infrastructure, worker integration, activity design, local dev setup, testing approach, and Docker/CI changes before delivering the repo’s first kernel schema.
- Existing FastAPI, Telegram, and storage code is repository-centric. Temporal would require a new composition pattern across apps and packages at the same time the kernel vocabulary is still being defined.
- The current worker is a simple polling process. Moving to Temporal is not just a library swap; it is a runtime model change.
- The immediate Phase 1 requirements do not yet need Temporal’s strongest advantages. Approval waits, replay semantics, and duplicate side-effect protection are mostly Phase 2 and 3 concerns.

Risks:

- The team may overfit the schema to Temporal execution history and underinvest in DB-native artifact lineage, even though the spec is artifact-driven and Postgres-first.
- Planning becomes muddier because Phase 1 would mix foundational domain modeling with infrastructure migration.

### Option B: Postgres-First Custom Runtime

Strengths for Helm:

- Matches the repo’s current architecture: SQLAlchemy repositories, Alembic migrations, polling worker, DB-first artifacts.
- Keeps one source of truth for run state, step state, artifacts, and validation outcomes.
- Makes Phase 1 narrow and concrete: define schema, repositories, orchestration service, and read APIs.
- Lets `packages/orchestration` become the durable state-transition boundary without forcing a new external runtime.
- Easier to expose Telegram/API views because operator surfaces can query one storage model directly.

Costs:

- Helm must own its own restart, step-claiming, retry bookkeeping, and blocked-state transitions.
- Later approval waits and long-lived timers will require careful runtime design instead of being inherited from Temporal.
- Recovery and replay semantics in Phase 3 will need explicit implementation discipline.

Risks:

- A poorly designed custom runtime can become an ad hoc workflow engine with unclear invariants.
- If step transitions are not atomic, the system can get duplicate attempts or misleading current-step state.

### Recommendation

For Phase 1, the planner should choose a Postgres-first custom runtime as the execution substrate.

That is not a claim that Temporal is wrong for Helm overall. It is a sequencing judgment: this repo needs its workflow vocabulary, durable validation model, and operator inspection shape before it can responsibly evaluate whether an external workflow engine is worth the added infrastructure. Phase 1 should therefore build the kernel around Postgres-owned run/step/artifact state and keep the orchestration service small enough that Temporal remains a later swap candidate if the custom runtime becomes limiting.

The planner should record this explicitly as a decision with a reevaluation trigger after Phase 3, when approval waits, retries, replay, and duplicate-write protection have been exercised.

## Recommended Implementation Shape

### Storage

Phase 1 should add new ORM models and migrations in `packages/storage` rather than reusing `AgentRunORM` as the kernel run table.

`agent_runs` should remain observability-oriented. It can later reference workflow runs, but it should not become the core workflow state machine because it lacks step identity, artifact lineage, validation outcomes, and durable blocked-state semantics.

Recommended new repositories:

- workflow runs repository
- workflow steps repository
- workflow artifacts repository
- workflow events repository

Repository contracts should follow the existing explicit dataclass style in `packages/storage/src/helm_storage/repositories/contracts.py`.

### Orchestration

Phase 1 should start moving durable workflow ownership into `packages/orchestration`.

Recommended package responsibilities:

- `packages/orchestration`: run creation, step transition rules, validation gating, blocked-state handling, and restart-safe “resume next runnable step” logic.
- `packages/agents`: specialist business logic only. In Phase 1 this can remain minimal or use placeholders for validation-driven artifacts.
- `apps/worker`: poll for runnable workflow steps and call orchestration services.
- `apps/api`: expose run status, artifact inspection, and operator actions like retry or terminate for blocked validation failures if implemented in this phase.
- `apps/telegram-bot`: read-only or lightweight run summaries for triage.

LangGraph can still be used inside a step implementation later, but the durable boundary should be “step started / step produced artifact / step validated / step blocked or succeeded,” not internal graph node history.

## Validation Architecture

Validation should be implemented as an explicit kernel boundary, not as ad hoc schema parsing inside whichever specialist produced an artifact.

Recommended model:

- A step produces a typed artifact candidate.
- A validator evaluates that candidate against the step contract.
- Validation persists a durable result record or artifact annotation with:
  - outcome: `passed`, `passed_with_warnings`, `failed`
  - machine-readable issues
  - human-readable summary
  - validator name and schema version
- The run transition logic advances only on `passed` or `passed_with_warnings`.
- `failed` moves the run to `blocked` and the step to `validation_failed`.

For this repo, validation should likely use Pydantic schemas at the boundary between orchestration and downstream consumers, because FastAPI already uses Pydantic and the codebase benefits from typed Python contracts. The persisted payload should still be JSON in Postgres so artifacts remain inspectable and schema-versioned.

Practical Phase 1 validation targets:

- raw workflow request artifact shape
- normalized task artifact shape
- final workflow summary artifact shape

The planner should not overbuild generic validator plugins yet. A registry local to `packages/orchestration` keyed by artifact type or step name is enough.

## Planning Implications By Roadmap Slice

### Plan 01-01: Persistence Foundation

Should cover:

- new ORM models and Alembic migration for runs, steps, artifacts, validation results or annotations, and events
- repository contracts and SQLAlchemy implementations
- enums/constants for statuses and artifact types
- basic restart-safe queries such as “list runnable runs” and “get run with latest step/artifacts”

Key caution:

- Keep schema separate from the email-specific artifact tables. Phase 1 should not attempt table unification across the whole repo.

### Plan 01-02: Typed Schemas And Validation Boundaries

Should cover:

- Pydantic models for run input and core artifacts
- orchestration service methods that create a run, start a step, persist candidate artifact, validate it, and commit the transition
- durable blocked-state behavior for validation failures
- retry or terminate action contract for blocked runs if included in Phase 1 scope

Key caution:

- The planner should make a clear atomicity rule. Example: a step attempt and its produced artifact should commit together, and the run current-step pointer should only move after validation outcome is persisted.

### Plan 01-03: Inspection Surfaces

Should cover:

- API read endpoints for run list/detail, current step, latest artifacts, validation failures, and needs-action filtering
- Telegram-friendly summaries sourced from the same read model
- status formatting that privileges triage over raw data volume

Key caution:

- Read models should be projections over the workflow tables, not custom status logic copied into API and bot layers.

## Open Decisions The Planner Should Resolve

- Whether validation results live as first-class rows or as structured fields on artifact versions. Separate rows are cleaner for lineage; embedded fields are simpler.
- Whether `workflow_events` is required in Phase 1 or whether step transitions plus timestamps already provide enough inspectability.
- Whether retry/terminate operator actions belong fully in Phase 1 or only the blocked-state schema and API visibility do.
- Whether `agent_runs` should gain an optional `workflow_run_id` foreign key in Phase 1 or remain untouched until the workflow kernel settles.

## Recommended Non-Goals For Phase 1

- No Temporal adoption yet.
- No approval request model yet beyond designing statuses to make Phase 2 additive.
- No adapter idempotency or replay semantics beyond preserving lineage fields that Phase 3 will need.
- No migration of current email triage flow onto the new kernel unless a thin demo path is needed to verify schema behavior.

## Validation And Testing Strategy

The planner should keep tests hermetic and mostly repository/service level.

Recommended test shape:

- repository tests for create/update/query behavior of runs, steps, artifacts, and blocked states
- orchestration service tests for valid advancement and validation-failure blocking
- API tests for run inspection endpoints
- one restart-oriented test that simulates an interrupted run and verifies the next runnable step is derived from stored state

The planner does not need end-to-end Temporal-style integration tests because the recommended Phase 1 substrate is Postgres-first.

## Bottom Line

Phase 1 should build a small durable workflow kernel in Postgres, centered in `packages/storage` and `packages/orchestration`, with explicit run, step, artifact, and validation state. The correct planning stance is to evaluate Temporal seriously, reject it for Phase 1 on sequencing and repo-fit grounds, and leave a clean seam for reevaluation after the kernel has proven its own invariants.