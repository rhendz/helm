# Phase 03 Research: Adapter Writes And Recovery Guarantees

## Objective

Plan Phase 03 so approved workflow proposals can produce external task/calendar writes through explicit adapter boundaries with durable lineage, restart-safe idempotency, partial-failure recovery, and clear retry versus replay semantics.

This phase is not just "add adapters." In this codebase, the real planning problem is how to turn an approved proposal artifact into a durable set of write intents that can survive retries, process restarts, and operator-driven recovery without duplicating side effects.

## What Already Exists

### Durable kernel state

- `packages/storage/src/helm_storage/models.py` already persists `workflow_runs`, `workflow_steps`, `workflow_artifacts`, `workflow_events`, `workflow_approval_checkpoints`, and `workflow_specialist_invocations`.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` already owns the lifecycle for:
  - run creation
  - step start/completion/failure
  - approval checkpoints
  - revision lineage
  - retry of a failed step within the same run
- `packages/orchestration/src/helm_orchestration/resume_service.py` already resumes runnable runs after restart by querying persisted run state.
- `apps/api/src/helm_api/services/workflow_status_service.py` already projects durable workflow state for operator surfaces and already has nullable final-summary sync fields ready for Phase 03.

### Important existing constraints

- Resume only knows how to dispatch specialist steps today. It does not know how to resume adapter-write steps.
- Retry is step-level today. It creates a new `workflow_steps` attempt and reruns the whole step.
- Replay exists only as a generic `replay_queue` scaffold for failed `agent_runs`; it is not workflow-lineage-aware and cannot safely replay external writes yet.
- Proposal approval is already anchored to a concrete artifact id and version. That is the right lineage anchor for sync.

## Planning-Critical Unknowns

These are the things that matter most to plan well.

### 1. Stable sync identity does not exist yet

Current schedule proposal payloads contain `time_blocks` and `proposed_changes`, but they do not carry stable item ids. That means Phase 03 cannot safely do idempotent external writes unless planning first decides how a single approved proposal version maps to deterministic write units.

You need one stable identity per outbound write candidate:

- `proposal_artifact_id`
- `proposal_version_number`
- `target_system`
- `sync_kind`
- `planned_item_key`

Without that, retry after partial success will devolve into fuzzy matching.

### 2. The kernel has step durability, but not intra-step durability

The current workflow model is strong for step transitions, but adapter writes are a multi-write side-effecting step. If one write succeeds and the next fails, the run can mark the step failed, but there is nowhere durable to record:

- which items were attempted
- which succeeded
- which external ids were created
- which are uncertain and need reconciliation
- which are safe to retry

Phase 03 needs item-level sync records, not only step-level events.

### 3. Retry and replay are not the same recovery action

The current retry flow is "same run, next step attempt." That is good for `RCVR-02`, but insufficient by itself for external writes.

For Phase 03:

- `retry` means continue or re-attempt unresolved/failed sync work within the same run and against the same approved proposal version
- `replay` means an explicit operator-triggered re-execution event with separate lineage to the original run/step, after reconciling prior sync facts

If the plan does not keep those semantics separate in storage and API language, the implementation will create ambiguous history.

### 4. Restart-safe resume must be driven by persisted sync facts, not in-memory progress

Current resume behavior can restart a step because run state is durable. For adapter writes, that is only safe if the step rehydrates from durable sync records and determines remaining work from the database every time it resumes.

Anything based on in-memory "already processed N items" is unacceptable for this phase.

## Standard Stack

Use the current repo stack. No new orchestration engine is required for this phase.

- SQLAlchemy ORM and repository pattern for durable sync state.
- Pydantic schemas in `packages/orchestration` for adapter write contracts and sync artifacts.
- `WorkflowOrchestrationService` as the owner of workflow semantics.
- `WorkflowResumeService` as the owner of restart-safe dispatch.
- Worker polling in `apps/worker` for executing runnable runs.
- API/Telegram read model extending the existing workflow status projection rather than adding a second sync-specific projection path.

For idempotency, use durable relational constraints, not application-only guards:

- unique constraints over sync identity columns
- transactional "get/create/mark-attempt" repository methods
- explicit persisted outcome states

## Architecture Patterns

### 1. Add a persisted sync-plan layer between approval and external write execution

Do not write directly from the approved proposal artifact.

Instead:

1. Approval of proposal version `N` resumes into a dedicated sync step.
2. That step derives a deterministic set of planned sync items from the approved artifact.
3. Those planned sync items are persisted before external calls happen.
4. Execution iterates those persisted items in deterministic order.

This gives Phase 03 a durable write manifest.

Recommended shape:

- `workflow_sync_records` table for one row per planned outbound write
- optional `workflow_sync_attempts` table only if you want first-class attempt history beyond events

Minimum row fields:

- `run_id`
- `step_id`
- `proposal_artifact_id`
- `proposal_version_number`
- `target_system`
- `sync_kind`
- `planned_item_key`
- `status`
- `idempotency_key`
- `external_object_id`
- `external_payload_fingerprint`
- `last_error`
- `last_attempted_at`
- `completed_at`
- `supersedes_sync_record_id` for deliberate replay/rewrite lineage if needed

Minimum unique constraints:

- unique on `(proposal_artifact_id, target_system, sync_kind, planned_item_key)`
- unique on `idempotency_key`

### 2. Keep orchestration as coordinator, adapters as side-effect boundary

Use explicit adapter protocols for task/calendar writes.

Recommended responsibility split:

- `packages/orchestration`
  - decides what should be written
  - decides ordering
  - owns recovery semantics
  - records sync state before and after adapter calls
- `packages/storage`
  - owns sync repositories and constraints
  - exposes transactional operations for claim/reconcile/update
- adapter implementation package
  - executes provider-specific create/update/delete/reconcile calls
  - returns normalized outcomes and discovered external ids

The adapter should not decide retry policy or run-state transitions.

### 3. Make sync execution a persisted step family, not a hidden helper

Do not keep "post-approval sync" as an internal side effect inside approval resolution.

Model it as an explicit step, for example:

- `prepare_adapter_writes`
- `execute_adapter_writes`

or a single step:

- `execute_approved_sync`

One-step or two-step can both work. The planning criterion is whether the execution can rebuild all needed work from persisted state after restart.

My recommendation: a single persisted execution step plus durable sync records is enough for V1. A separate preparation step only helps if you want the write manifest inspectable before calls begin.

### 4. Reconcile before retry when outcome is uncertain

Adapter write results should not be binary "success/fail."

Use at least these sync states:

- `pending`
- `in_progress`
- `succeeded`
- `failed_retryable`
- `failed_terminal`
- `uncertain_needs_reconciliation`
- `cancelled`

If the process crashes after sending a request but before persisting success, the next resume path must:

1. load the sync record
2. detect uncertain prior attempt
3. call adapter reconcile using durable identity and/or provider lookup
4. mark success if the object already exists
5. retry create/update only if reconciliation shows no prior success

### 5. Preserve partial success as first-class state

If task writes succeed and a calendar write fails, the run should fail with partial sync lineage intact.

Do not collapse partial success into one final error string.

The read model should be able to answer:

- how many writes succeeded
- how many failed
- how many are unresolved
- which write failed last
- which external object ids already exist

### 6. Keep replay lineage separate from retry lineage

Recommended model:

- retry stays within the same `workflow_run`
- retry creates a new step attempt for the same step
- replay creates a new workflow event and either:
  - a new run linked to the original run, or
  - a replay artifact/event within the same run plus new sync records linked to prior ones

For V1, the simplest safe choice is:

- keep retry in the same run
- make replay an explicit event plus new sync attempt lineage against existing sync records

If planning cannot make same-run replay semantics clear, choose new-run replay with explicit `replayed_from_run_id` lineage. That is easier to reason about than overloading retry.

## Recommended Schema Additions

### New artifact/schema concepts

Add typed schemas for:

- approved sync execution plan
- sync item result
- sync failure summary
- replay request lineage

These can remain inside `packages/orchestration/schemas.py` and flow into `workflow_artifacts` or final summary payloads.

### New storage model

Add a dedicated sync model instead of trying to encode everything in `workflow_events.details`.

Why:

- events are append-only summaries, not queryable idempotency state
- operator views need counts by sync state
- resume needs indexed lookups for remaining work
- uniqueness constraints belong on a real table

### Final summary extension

The existing final summary already supports:

- `downstream_sync_status`
- `downstream_sync_artifact_ids`
- `downstream_sync_reference_ids`

Use those fields as a summary pointer only. Do not treat the final summary as the source of truth for sync state.

## Repository And Module Boundaries

### Recommended file ownership

- `packages/storage`
  - new ORM model(s)
  - repositories for sync records and reconciliation queries
- `packages/orchestration`
  - sync schemas
  - adapter protocol contracts
  - workflow service changes for post-approval sync execution, retry, terminate, and replay lineage
  - resume service dispatch support for sync steps
- `apps/worker`
  - register sync step handlers in workflow run job
- `apps/api`
  - extend workflow status/read model and add explicit replay endpoints only if Phase 03 includes operator controls

### Where adapter implementations should live

The repo’s boundary note says `packages/connectors` is for external system ingress, but Phase 03 needs outbound provider boundaries too. Planning should decide one of these and stay consistent:

- Option A: put task/calendar adapter implementations in `packages/connectors` because they are still external system boundary code
- Option B: create a new adapter-focused package later

For this phase, Option A is the pragmatic choice. Keep protocol definitions near orchestration, implementations near connectors.

## Don’t Hand-Roll

- Do not hand-roll idempotency with only "check then create" logic in Python. Use database uniqueness plus reconciliation.
- Do not store sync state only in JSON event blobs.
- Do not infer whether a write already happened from proposal content alone.
- Do not make replay "just call retry again."
- Do not attempt rollback/compensation for already-succeeded writes in V1.
- Do not rely on worker memory, job-local caches, or loop indexes for resume safety.
- Do not couple adapter providers directly to `WorkflowRunORM` or API response shaping.

## Common Pitfalls

### Missing stable planned-item keys

If a time block has only title/start/end and no stable write key, small proposal formatting changes will break idempotency and reconciliation.

Planning implication:

- define planned item keys explicitly in the approved proposal or a derived sync-plan artifact

### Step retry that replays already-succeeded writes

Current retry semantics create a new step attempt and rerun the step. Without per-item sync records, this will duplicate successful writes on partial failure.

Planning implication:

- retry path must query sync records and only operate on failed or unresolved items

### Approval-to-sync transition that hides execution lineage

If approval resolution directly calls adapters and only records a final status, operator inspection and recovery will be weak.

Planning implication:

- persist sync work before execution starts

### Ambiguous uncertain outcomes

Network timeout after provider accepted a create is the classic failure mode.

Planning implication:

- adapters need a `reconcile` capability, not only `apply`

### Same-run replay without explicit lineage

If replay mutates existing sync rows in place, the history becomes unreadable.

Planning implication:

- replay must append lineage, not overwrite it

### Termination after partial success

Current terminate behavior cancels the current step and marks the run terminated. With sync in play, already-succeeded sync rows must remain durable and untouched.

Planning implication:

- terminate must stop further writes but preserve partial lineage and surfaced counts

## Codebase-Specific Recommendations

### Recommendation 1: introduce a sync repository before adapter code

In this repo, storage-first is the right order.

Phase 03 should plan storage/repository work first because:

- resume safety depends on durable sync state
- the orchestrator cannot be designed cleanly until sync query/update operations exist
- API status projections need sync read paths anyway

### Recommendation 2: extend `WorkflowResumeService` to dispatch semantic sync steps

Today it only dispatches specialist steps keyed by `(workflow_type, step_name)`.

Phase 03 should extend that same dispatch mechanism for sync execution steps rather than creating a separate worker job path. That keeps restart behavior consistent.

### Recommendation 3: keep the first deterministic order simple and explicit

Choose one order for V1 and encode it in the sync manifest.

Recommended default:

1. task-system writes
2. calendar writes

This matches the phase context and makes partial success easier to explain in operator views.

### Recommendation 4: use operator surfaces already in place

Do not build a second read model.

Extend the existing workflow status projection so API and Telegram both see:

- sync counts by state
- last failed write summary
- approved proposal version
- downstream references

### Recommendation 5: treat current replay queue as unrelated scaffolding

The existing `replay_queue` is agent-run oriented and should not be stretched into workflow sync replay semantics unless the plan explicitly reworks it.

For Phase 03 planning, assume workflow replay needs dedicated lineage semantics.

## Code Examples

### Sync record repository contract

```python
@dataclass(frozen=True, slots=True)
class NewWorkflowSyncRecord:
    run_id: int
    step_id: int
    proposal_artifact_id: int
    proposal_version_number: int
    target_system: str
    sync_kind: str
    planned_item_key: str
    idempotency_key: str
    payload: dict[str, Any]
    status: str = "pending"


class WorkflowSyncRepository(Protocol):
    def create_or_get(self, record: NewWorkflowSyncRecord) -> WorkflowSyncRecordORM: ...
    def list_for_step(self, run_id: int, step_id: int) -> list[WorkflowSyncRecordORM]: ...
    def list_retryable_for_run(self, run_id: int) -> list[WorkflowSyncRecordORM]: ...
    def mark_in_progress(self, sync_id: int) -> WorkflowSyncRecordORM | None: ...
    def mark_succeeded(self, sync_id: int, *, external_object_id: str | None) -> WorkflowSyncRecordORM | None: ...
    def mark_failed(self, sync_id: int, *, retryable: bool, error_summary: str) -> WorkflowSyncRecordORM | None: ...
    def mark_uncertain(self, sync_id: int, *, error_summary: str) -> WorkflowSyncRecordORM | None: ...
```

### Adapter protocol

```python
class AdapterWriteResult(BaseModel):
    status: Literal["succeeded", "already_applied", "uncertain", "failed"]
    external_object_id: str | None = None
    provider_reference: str | None = None
    error_summary: str | None = None


class SyncAdapter(Protocol):
    def apply(self, item: SyncExecutionItem) -> AdapterWriteResult: ...
    def reconcile(self, item: SyncExecutionItem) -> AdapterWriteResult: ...
```

### Resume-safe execution loop

```python
def execute_sync_step(run_id: int) -> WorkflowRunState:
    state = workflow_service.start_current_step(run_id)
    sync_items = sync_repo.list_retryable_for_run(run_id)

    for item in sync_items:
        if item.status == "succeeded":
            continue

        claimed = sync_repo.mark_in_progress(item.id)
        if claimed is None:
            continue

        result = adapter.reconcile(build_execution_item(claimed))
        if result.status in {"succeeded", "already_applied"}:
            sync_repo.mark_succeeded(claimed.id, external_object_id=result.external_object_id)
            continue

        result = adapter.apply(build_execution_item(claimed))
        if result.status in {"succeeded", "already_applied"}:
            sync_repo.mark_succeeded(claimed.id, external_object_id=result.external_object_id)
        elif result.status == "uncertain":
            sync_repo.mark_uncertain(claimed.id, error_summary=result.error_summary or "uncertain outcome")
        else:
            sync_repo.mark_failed(claimed.id, retryable=True, error_summary=result.error_summary or "adapter write failed")

    return finalize_step_from_sync_rows(run_id)
```

## Suggested Planning Sequence

Plan the phase in this order:

1. Define sync identity, sync states, and replay vocabulary.
2. Add storage model and repositories for durable sync records.
3. Add orchestration schemas and adapter protocols.
4. Add post-approval sync step dispatch and resume support.
5. Add retry behavior that consumes sync-record state.
6. Extend operator/API status projections with sync summaries.
7. Add explicit replay lineage behavior.
8. Add tests for partial success, uncertain outcome, retry, replay, terminate-after-partial-success, and restart-safe resume.

## Verification Targets For The Plan

The eventual plan should prove all of these:

- same approved proposal is not duplicated across retry
- restart after one successful external write does not repeat that write
- uncertain write outcome reconciles before retrying
- partial success is visible in status/detail endpoints
- terminate after partial success preserves succeeded sync lineage
- replay is operator-triggered and has explicit lineage distinct from retry
- final summary links to downstream sync results but is not the only sync truth

## Confidence

- High confidence:
  - storage-first approach
  - need for item-level sync records
  - keeping retry distinct from replay
  - extending existing workflow read model
- Medium confidence:
  - exact schema split between sync records and sync attempts
  - whether replay should be same-run or new-run in V1
- Low confidence:
  - final provider-specific adapter shapes, because task/calendar target systems are not implemented yet
