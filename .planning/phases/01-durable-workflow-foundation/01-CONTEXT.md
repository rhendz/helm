# Phase 1: Durable Workflow Foundation - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the kernel's durable workflow run, step, artifact, and validation model. This phase defines the foundation for reliable execution, inspectable lineage, and blocked-state handling, but it does not yet add approval semantics, downstream adapter writes, or broader workflow scope.

</domain>

<decisions>
## Implementation Decisions

### Workflow vocabulary
- The top-level durable object should be a `workflow run`, not a generic job or loose case record.
- Major execution boundaries should be stored as explicit named steps with durable identity, status, and timestamps.
- Intermediate outputs should be persisted as versioned typed artifacts rather than only storing a single latest value or opaque step snapshots.
- Phase 1 should establish a kernel-native vocabulary cleanly and map older domain-specific persistence concepts toward it over time, rather than inheriting the current email-specific artifact model as the core contract.

### Validation behavior
- Specialist outputs must be schema-valid before they can advance the workflow.
- Malformed, incomplete, or materially ambiguous specialist outputs should fail validation and move the run into a blocked durable state.
- Validation failures should be durable, inspectable, and should prevent downstream execution until the workflow is explicitly retried, revised, or terminated.
- Non-fatal warnings should be persisted as annotations alongside valid artifacts and should not block execution if the artifact still satisfies the current step contract.
- In Phase 1, blocked validation-failure runs should support explicit retry or terminate actions; richer revision behavior belongs in later phases.

### Run visibility
- The default operator view should optimize for triage: what run this is, what step it is on, what happened last, and whether it needs action now.
- Phase 1 should expose step and artifact lineage without requiring raw database inspection.
- Runs that need operator attention should have explicit "needs action" style cueing rather than requiring inference from status alone.
- Telegram should remain the concise primary operator surface for request submission, run summaries, and lightweight recovery handling.
- The API should expose deeper run, artifact, validation, and recovery detail than Telegram.

### Research direction to lock before planning
- Phase 1 research/planning should explicitly evaluate Temporal against a Postgres-first custom runtime for durable execution.
- This is a required evaluation topic, not a forced decision to adopt Temporal in v1.
- The goal is to lock the durable-execution substrate intentionally during planning rather than assume it upfront.

### Claude's Discretion
- Exact schema names, table layout, and repository boundaries within the chosen workflow vocabulary.
- Exact presentation format for status/read views as long as triage-first visibility is preserved.
- The precise mechanism used to expose lineage in API and Telegram surfaces.

</decisions>

<specifics>
## Specific Ideas

- The foundation should be trustworthy first: strict correctness for step advancement, with durable warnings and blocked states rather than "best effort" progression.
- The default operator question is operational: "What run is this in, what step is it on, what happened last, and does it need action now?"
- Long-running, approval-gated workflows may wait across time boundaries, which is why Temporal should be evaluated explicitly against a Postgres-first custom runtime before locking the substrate.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/storage/src/helm_storage/models.py`: existing durable ORM patterns and table ownership can anchor new workflow-run and artifact models.
- `packages/storage/src/helm_storage/repositories/contracts.py`: existing repository contract style can guide typed workflow payloads and persistence interfaces.
- `apps/api/src/helm_api/routers/` and `apps/api/src/helm_api/services/`: existing thin API entrypoint pattern can expose run status and artifact inspection without inventing a new surface.
- `apps/telegram-bot/src/helm_telegram_bot/commands/` and `apps/telegram-bot/src/helm_telegram_bot/services/`: existing Telegram command/service split can support concise run summaries later.
- `packages/observability/src/helm_observability/agent_runs.py`: existing run-tracking behavior may inform naming or lifecycle expectations for kernel run records.

### Established Patterns
- App layer orchestrates; package layer implements reusable behavior.
- Postgres-backed SQLAlchemy models are already the durable source of truth.
- Repository contracts are explicit and boring; Phase 1 should fit that style rather than introduce magic abstractions.
- Structured logging and persisted execution records already exist and should complement, not replace, durable workflow state.

### Integration Points
- `packages/orchestration/` is currently the intended but mostly empty kernel boundary where Phase 1 work should concentrate.
- `packages/storage/` will be the main integration point for workflow runs, steps, artifacts, and validation records.
- API and Telegram surfaces should read from the new durable workflow state rather than invent parallel status models.

</code_context>

<deferred>
## Deferred Ideas

- Approval, reject, and revision flow as a full operator experience belongs to Phase 2.
- Downstream task-system and calendar writes belong to Phase 3.
- Generalized dynamic routing and broader specialist orchestration remain later-version concerns.

</deferred>

---
*Phase: 01-durable-workflow-foundation*
*Context gathered: 2026-03-12*
