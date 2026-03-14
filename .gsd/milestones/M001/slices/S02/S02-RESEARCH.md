# Phase 02 Research: Specialist Dispatch And Approval Semantics

## Objective

Answer the planning question for Phase 02: what must be understood before breaking implementation into plans for specialist dispatch, approval checkpoints, revision lineage, and resume semantics.

Primary requirement coverage for this phase:

- `AGNT-01`
- `AGNT-02`
- `AGNT-03`
- `ARTF-04`
- `APRV-01`
- `APRV-02`
- `APRV-03`
- `APRV-04`
- `APRV-05`
- `APRV-06`
- `DEMO-02`
- `DEMO-03`

## Source Of Truth

- Product/source-of-truth doc: `docs/internal/helm-v1.md`
- Phase context: `.planning/phases/02-specialist-dispatch-and-approval-semantics/02-CONTEXT.md`
- Current durable kernel decisions: `.planning/REQUIREMENTS.md`, `.planning/STATE.md`

Relevant source-of-truth constraints:

- V1 defaults to approval for meaningful outbound actions.
- Internal artifact creation and draft generation are safe to automate without approval.
- The system should stay simple, Postgres-first, Telegram-first, and extensible to future specialists.

## What Already Exists

### Durable kernel foundation is in place

- `packages/orchestration/src/helm_orchestration/workflow_service.py` already owns run creation, step transitions, validation blocking, retry, terminate, and final summary assembly.
- `packages/orchestration/src/helm_orchestration/resume_service.py` already resumes runnable runs through registered step handlers.
- `packages/storage/src/helm_storage/models.py` already has `workflow_runs`, `workflow_steps`, `workflow_artifacts`, and `workflow_events`.
- `workflow_artifacts` already supports `version_number`, `lineage_parent_id`, and `supersedes_artifact_id`.
- API and Telegram already share a single workflow status read model via `apps/api/src/helm_api/services/workflow_status_service.py`.

### The current gaps are structural, not foundational

- Specialist dispatch is currently only an in-memory `step_name -> handler` mapping in the worker; there is no typed dispatch contract yet.
- Approval is represented in read models only as placeholder fields on final summary output; there is no write path for workflow approvals.
- Resume semantics only cover runnable runs and failed-step retry; there is no approval-driven continuation path.
- Artifact lineage exists generically, but proposal-specific artifacts and approval-specific artifacts do not yet exist.

## Standard Stack

Use the stack already established in this repo:

- `packages/orchestration`: own workflow step execution semantics and typed step results.
- `packages/storage`: own durable schemas, repositories, and migrations for new workflow artifacts and approval records.
- `apps/worker`: own handler registration and background resumption of runnable runs.
- `apps/api`: own workflow operator actions for approve, reject, and request revision.
- `apps/telegram-bot`: own Telegram command/interaction surfaces for pending approvals and revisions.
- Pydantic schemas in `packages/orchestration/src/helm_orchestration/schemas.py`: own specialist input/output payload contracts.
- Postgres-backed workflow tables: remain the source of truth for run state, artifacts, events, and lineage.

Do not introduce a second workflow state system for this phase.

## Architecture Patterns

### 1. Keep workflow control in the kernel, not in Telegram commands

Approval decisions should be operator inputs into the workflow kernel, not standalone bot-side mutations. Telegram and API should call a workflow operator service that:

- validates the requested action against the current blocked checkpoint
- writes durable approval/revision artifacts and events
- updates run state atomically
- either advances the step pointer or creates the next step attempt

This preserves a single control plane and satisfies `APRV-03` and `APRV-04`.

### 2. Model specialist execution as explicit workflow steps with typed contracts

Phase 2 should plan around a representative scheduling workflow with explicit steps such as:

1. `normalize_request_for_task_agent`
2. `dispatch_task_agent`
3. `dispatch_calendar_agent`
4. `await_schedule_approval`
5. terminal summary or handoff to later sync steps

The key point is not the exact names. The key point is that specialist invocation must be visible in workflow state and step history.

Use typed specialist envelopes, not raw dicts passed ad hoc through handlers:

- `TaskAgentInput`: raw request text, workflow metadata, already-known constraints
- `TaskAgentOutput`: normalized task artifact plus warnings/ambiguities
- `CalendarAgentInput`: validated normalized tasks plus scheduling constraints
- `CalendarAgentOutput`: schedule proposal artifact plus warnings/ambiguities

This is necessary for `AGNT-01`, `AGNT-02`, `DEMO-02`, and `DEMO-03`.

### 3. Dispatch should be keyed by workflow semantics, not only step name

Today the resume path dispatches only by `step_name`. That is too weak for a reusable kernel.

Plan for a registry keyed by one of:

- `(workflow_type, step_name)`, or
- explicit step handler objects attached to a workflow definition

Do not keep specialist selection as loose worker wiring. The planner should assume the dispatch contract belongs in `packages/orchestration` and is consumed by `apps/worker`.

### 4. Approval should be an explicit blocked checkpoint, not a failed retry case

Validation failures already use `blocked + needs_action + awaiting_operator`. Approval checkpoints should reuse the same high-level run state shape, but not the same meaning as a failure.

Plan a first-class approval checkpoint flow:

1. specialist produces a schema-valid proposal artifact
2. workflow writes an approval-request artifact tied to that proposal version
3. run moves to `blocked` with `needs_action=true`
4. operator chooses approve, reject, or request revision
5. workflow records decision and either:
   - advances past the checkpoint
   - terminates cleanly
   - re-enters the proposal-producing step with revision feedback

This is the cleanest path for `APRV-01` through `APRV-04`.

### 5. Revision should create new proposal versions inside the same run

The phase context is explicit: revision stays inside the same workflow run and creates a new version instead of overwriting.

Plan revision lineage as:

- original proposal artifact
- revision request artifact referencing that proposal
- revised proposal artifact with:
  - `lineage_parent_id` pointing to the upstream input or approval request context
  - `supersedes_artifact_id` pointing to the prior proposal version

The approval decision artifact should always reference the exact proposal version it resolved. That is required for `APRV-05` and `APRV-06`.

### 6. Latest-first views should be read-model logic, not data loss

The operator default view should show the latest proposal version, but older versions must remain queryable.

That means:

- storage keeps all versions
- status/detail services choose latest by artifact type/version
- Telegram default rendering stays compact
- API detail returns the full artifact lineage

This aligns with existing `latest_artifacts` behavior and avoids creating a separate “current proposal” store.

## Data Model Guidance

### New artifact types are the main missing piece

Current artifact types are too narrow: `raw_request`, `normalized_task`, `validation_result`, `final_summary`.

Phase 2 likely needs additional workflow artifact types for planning:

- `task_agent_invocation`
- `normalized_task`
- `calendar_agent_invocation`
- `schedule_proposal`
- `approval_request`
- `approval_decision`
- `revision_request`

The exact names can vary, but separate proposal artifacts from approval artifacts. Do not overload `validation_result` or `final_summary`.

### Specialist invocation records should be durable artifacts or a dedicated table

Requirement `AGNT-03` requires input reference, output reference, timing, and result status for each specialist execution.

Two viable approaches:

1. Dedicated `workflow_specialist_invocations` table.
2. Artifact-based invocation records plus workflow events.

For this repo, a dedicated table is the better planning default if you want clean querying by specialist execution. It avoids stuffing execution metadata into proposal payloads and keeps `workflow_artifacts` focused on business artifacts.

Minimum invocation fields:

- `run_id`
- `step_id`
- `specialist_name`
- `input_artifact_id` or input reference payload
- `output_artifact_id`
- `status`
- `started_at`
- `completed_at`
- `error_summary`

If the team wants to stay smaller in Phase 2, artifact-plus-event can work, but only if the schema is explicit and queryable enough to satisfy `AGNT-03`.

### Approval records need durable action semantics

Approval persistence must include:

- checkpoint/request artifact or table row
- allowed actions at the time of pause
- final decision
- actor
- timestamp
- target proposal artifact id
- revision feedback when present

This is required for `APRV-03` and helps with `APRV-06`.

### Reuse artifact lineage; do not invent a separate revision store

The generic lineage fields already exist. Plan to extend them rather than adding a bespoke revision subsystem.

That means:

- proposal versions use `supersedes_artifact_id`
- approval or revision artifacts point back to the proposal version they reference
- read models reconstruct “approved”, “rejected”, and “superseded” from existing lineage and decision records

### Final summary contract should remain nullable-friendly

Phase 1 intentionally froze nullable approval linkage fields on final summary artifacts. Keep that contract stable and populate it later from approval artifacts rather than redesigning it now.

## Step And Resume Semantics

### Separate three operator-intervention modes

The plan must keep these distinct:

- validation-blocked: output schema invalid
- approval-blocked: waiting for human decision on a valid proposal
- execution-failed: specialist or step execution failed technically

Do not collapse approval into retry semantics. Retry means “same step attempt again after failure.” Revision means “new proposal version based on feedback.” Approval means “checkpoint resolved; proceed.”

### Approval-driven resume should not require manual worker prompting

The spec says the runner should resume without manual re-prompting unless blocked by human decision. For this phase, that implies:

- while waiting for approval: run is blocked and excluded from worker runnable scans
- on approve/reject/revision: the operator action updates run state so the worker can pick it up automatically, or directly advances within the same transaction if that is simpler

Do not require an operator to both approve and separately resume.

### Revision should restart at the proposal-producing specialist step

This is explicitly called out in phase context and should drive planning.

For the representative scheduling workflow:

- revision after schedule proposal should re-enter the `CalendarAgent` proposal step
- it should use the latest validated tasks plus revision feedback
- it should not restart the `TaskAgent` normalization step unless the revision invalidates task assumptions

The planning breakdown should decide whether revision feedback becomes:

- part of the new step input envelope, or
- a durable `revision_request` artifact that the step handler reads

The second option is better for replayability and inspection.

## Read Model And UX Guidance

### API should remain the richer inspection surface

`WorkflowStatusService` already has the right shape for deeper operator detail:

- paused state
- pause reason
- available actions
- artifact lineage
- step transitions
- events

Plan to extend this service rather than creating separate approval-specific read logic elsewhere.

### Telegram should stay compact but action-complete

Telegram is the decision surface, not the archival surface.

For planning, assume Telegram needs:

- compact proposal summary
- why Helm is paused
- allowed actions: approve, reject, request revision
- optional hint on what each action does next

It does not need to render full lineage by default, but it should be able to link or reference the exact run/proposal version being acted on.

### Unify operator terminology

Current workflow surfaces say `retry` and `terminate`. Legacy draft flows say `approve` and `snooze`.

Before planning tasks, settle the workflow vocabulary:

- `approve`
- `reject`
- `request_revision`

Keep `retry` for technical or validation failures only.

## Don’t Hand-Roll

- Do not build a second approval state machine outside `workflow_runs` and `workflow_steps`.
- Do not store only “current proposal” and discard older versions.
- Do not treat revision as in-place mutation of an artifact payload.
- Do not use Telegram message state as the source of truth for pending approvals.
- Do not encode all approval semantics only in freeform workflow events without typed artifacts or structured records.
- Do not route specialist behavior through hard-coded bot commands.

## Common Pitfalls

- Confusing approval checkpoints with validation failure blocks. They both pause the run, but they require different actions and history.
- Keying dispatch only by `step_name`, which will become ambiguous as more workflows are added.
- Storing revision feedback only in Telegram text without a durable artifact reference.
- Allowing approval commands to operate without checking the currently pending checkpoint, which will break idempotency and replay safety.
- Overloading `final_summary` as a place to persist all approval state instead of using first-class approval artifacts.
- Making Telegram the only place that knows which proposal version is current.
- Recomputing lineage in app code from domain tables when workflow artifacts already provide the durable chain.

## Recommended Planning Slices

The phase will plan better if broken into slices that preserve kernel-first boundaries:

### Slice 1: Specialist contracts and dispatch registry

- define typed input/output schemas for `TaskAgent` and `CalendarAgent`
- add workflow-aware handler registration
- implement representative step sequence for scheduling flow

### Slice 2: Storage changes for invocation, proposal, and approval artifacts

- add artifact types and any new repository/table support
- persist specialist invocation records
- persist schedule proposal artifacts and lineage fields

### Slice 3: Approval checkpoint semantics

- add orchestration methods for checkpoint creation and operator decision handling
- distinguish approval-blocked state from validation failure and execution failure
- ensure automatic worker continuation after decision

### Slice 4: Revision lineage and re-entry behavior

- persist revision requests
- create superseding proposal versions
- resume from the proposal-producing specialist step

### Slice 5: Operator surfaces and read models

- extend API actions and detail views
- add Telegram approve/reject/request-revision interactions
- render latest-first while preserving full version inspectability

## Test Planning Guidance

The plan should include tests at three levels.

### Unit tests

- typed schema validation for `TaskAgentInput`, `TaskAgentOutput`, `CalendarAgentInput`, `CalendarAgentOutput`
- dispatch registry resolution by workflow type and step
- approval action validation against allowed actions
- revision lineage creation and latest-version selection

### Integration tests

- representative scheduling flow: raw request -> normalized tasks -> schedule proposal -> approval checkpoint
- approve path resumes from the correct step without duplicate proposal creation
- reject path records final decision and leaves run terminal or blocked as designed
- revision path creates a new proposal version and preserves superseded history
- specialist invocation records include timing, status, and input/output references

### Read-model tests

- API detail shows pending checkpoint, latest proposal version, and older proposal lineage
- Telegram formatting shows pause reason and action choices without exposing low-value internals
- approved/rejected/superseded proposal version is queryable from workflow detail

## Code Examples

### Example planning shape for step results

```python
@dataclass(frozen=True, slots=True)
class SpecialistStepResult:
    artifact_type: WorkflowArtifactKind
    payload: object
    next_step_name: str | None = None
    invocation_record: SpecialistInvocationPayload | None = None
```

This keeps specialist execution metadata explicit instead of burying it in event details.

### Example approval action contract

```python
class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


class ApprovalDecisionPayload(BaseModel):
    run_id: int
    checkpoint_artifact_id: int
    proposal_artifact_id: int
    decision: ApprovalDecision
    actor: str
    comment: str | None = None
```

This makes `APRV-02`, `APRV-03`, and `APRV-06` plannable without mixing them into generic retry requests.

### Example revision lineage rule

```python
new_proposal = NewWorkflowArtifact(
    run_id=run_id,
    step_id=step_id,
    artifact_type="schedule_proposal",
    schema_version=SCHEMA_VERSION,
    producer_step_name="dispatch_calendar_agent",
    lineage_parent_id=revision_request_artifact_id,
    supersedes_artifact_id=prior_proposal_artifact_id,
    payload=proposal.model_dump(mode="json"),
)
```

This matches the phase decision that revisions stay in the same run and produce new versions.

## Planning Decisions To Lock Before Writing Plans

The phase should answer these before plan decomposition:

1. Will specialist invocation persistence be a dedicated table or artifact-plus-event only?
2. What exact workflow step sequence proves `TaskAgent -> CalendarAgent -> approval checkpoint`?
3. Will approval checkpoints be represented as blocked steps with a dedicated artifact type, a dedicated table, or both?
4. Does operator approval directly advance the run, or does it only make the run runnable for the worker?
5. What is the exact lineage relationship between `revision_request`, `schedule_proposal`, and `approval_decision` artifacts?
6. Which read model becomes the source for “latest proposal version” and “approved version” in API and Telegram?
7. Is snooze explicitly in scope for this phase, or deferred behind the core approve/reject/request-revision loop?

## Bottom Line

This phase does not need a new workflow system. It needs to extend the existing durable kernel so specialist dispatch, proposal generation, approval checkpoints, and revision-driven resume all become first-class workflow concepts.

The most important planning choice is to keep workflow artifacts and workflow state as the control plane:

- typed specialist contracts in orchestration
- durable invocation/proposal/approval records in storage
- checkpoint and decision handling in the workflow service
- API and Telegram as thin operator surfaces over the same read/write model

If the plans hold that boundary, the phase can satisfy the specialist, approval, revision, and resume requirements without rework in Phase 3 and Phase 4.