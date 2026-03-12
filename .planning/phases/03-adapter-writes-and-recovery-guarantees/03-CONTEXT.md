# Phase 3: Adapter Writes And Recovery Guarantees - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Make approved workflow proposals execute through task-system and calendar adapter boundaries with durable sync lineage, strong idempotency, and safe retry, resume, and replay behavior. This phase defines how approved proposal items become external writes and how recovery behaves when sync work partly or fully succeeds, but it does not expand product scope beyond the representative scheduling workflow.

</domain>

<decisions>
## Implementation Decisions

### Write boundary
- Approval should authorize item-level downstream writes under one approved proposal rather than a single opaque bulk sync result.
- Every downstream write must anchor to the exact approved proposal version, not an implied latest workflow state.
- After approval, Helm should automatically proceed into downstream writes in a predictable order without requiring a second confirmation step.
- The default operator view before execution should show a compact effect summary such as how many task and calendar writes approval will trigger.

### Idempotency model
- The primary sync identity should be per planned item and target system, scoped under the exact approved proposal version.
- If Helm determines that a write already succeeded earlier, it should record the existing linkage and continue rather than attempting another create or update blindly.
- When a write outcome is uncertain, Helm should reconcile first and retry only if needed.
- Duplicate protection must survive restart and resume as a hard durability requirement; process restarts must not weaken sync safety.

### Failure handling
- If some downstream writes succeed and later ones fail, the run should remain failed with itemized sync state rather than collapsing to a generic error.
- The primary recovery action should retry only failed or unresolved writes, not replay already-successful writes by default.
- The default operator view after a sync failure should show the last failed write and counts by sync state.
- If approval is revoked or the run is terminated after partial success, Helm should preserve a terminal state with partial sync lineage and stop further execution.

### Replay semantics
- Replay should exist only on explicit operator intent; it is not an automatic recovery path.
- A replay should create a new replay event linked to the prior run or step rather than mutating history in place or pretending to be a fresh unrelated execution.
- Replay of external writes should require deliberate targeting and reconciliation against known prior sync lineage.
- Operator-facing language should make replay explicit as an intentional re-execution action with preserved lineage, not merely a stronger retry.

### Claude's Discretion
- Exact adapter contract shapes, repository names, and sync-record schema as long as write identity and recovery lineage remain explicit.
- Whether the first write order is task-first then calendar-first or another deterministic order, provided the order is consistent and visible.
- How much operator-facing sync detail belongs in the compact default view versus on-demand inspection routes.

</decisions>

<specifics>
## Specific Ideas

- Approved proposal execution should feel automatic and predictable, with recovery actions driven by durable sync facts rather than extra prompts.
- Partial sync should never be hidden; Helm should make it obvious what already happened and what still needs reconciliation.
- Replay must stay semantically distinct from retry because external writes may already exist.
- The overlap between Helm’s needs and durable workflow engine concerns has become more explicit by Phase 3: pause/resume, approval waits, retry versus replay, restart safety, idempotency, and partial failure recovery all strengthen the case for Helm to keep product semantics while evaluating Temporal or a similar substrate as a future execution engine.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/orchestration/src/helm_orchestration/workflow_service.py`: already owns specialist execution, approval checkpoints, and proposal version lineage that Phase 3 can extend into adapter write steps.
- `apps/api/src/helm_api/services/workflow_status_service.py`: already projects approval and version state from durable records and can extend to sync-state visibility.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`: already provides concise operator views for runs, approvals, and proposal versions that can grow into sync and recovery summaries.
- `packages/agents/src/email_agent/adapters/helm_runtime.py`: existing adapter-style runtime code demonstrates the repo’s preference for wrapping external-system actions behind explicit runtime boundaries.
- `apps/api/src/helm_api/services/replay_service.py` and `apps/worker/src/helm_worker/jobs/replay.py`: existing replay concepts can inform operator language and lineage expectations without collapsing replay into retry.
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`, `workflow_events.py`, `workflow_runs.py`, and approval/specialist repositories: current durable kernel state already supports explicit linkage between proposals, decisions, and later sync artifacts.

### Established Patterns
- External side effects should flow through adapter-style boundaries rather than directly from workflow logic.
- Operator surfaces stay thin and consume one shared durable read model.
- Workflow history is DB-first and artifact-driven; new sync state should fit that same pattern instead of introducing transient write tracking.
- Retry, blocked, failed, and approval states are already modeled separately and should remain distinct once sync behavior is added.

### Integration Points
- Adapter write execution should plug into the existing workflow step machinery after approval resolution rather than forming a parallel execution path.
- Sync lineage should extend the current proposal, approval, and final-summary artifacts so the exact approved version can be tied to external object ids and attempt outcomes.
- Replay semantics should connect to the existing run, step, event, and replay-service concepts instead of inventing an unrelated rerun mechanism.

</code_context>

<deferred>
## Deferred Ideas

- Automatic compensation or rollback of already-succeeded downstream writes.
- Richer object-by-object default operator previews before approval.
- A full execution-substrate migration decision; Temporal remains an explicit research direction, not a locked implementation choice for this phase.

</deferred>

---
*Phase: 03-adapter-writes-and-recovery-guarantees*
*Context gathered: 2026-03-12*
