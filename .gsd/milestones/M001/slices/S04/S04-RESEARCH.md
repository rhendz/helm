# Phase 04 Research: Representative Scheduling Workflow

## Objective

Answer the planning question for Phase 04: what must be understood before breaking implementation into plans for the representative weekly scheduling workflow.

Primary requirement coverage for this phase:

- `DEMO-01`
- `DEMO-04`
- `DEMO-05`
- `DEMO-06`

## Source Of Truth

- Product/source-of-truth doc: `docs/internal/helm-v1.md`
- Phase context: `.planning/phases/04-representative-scheduling-workflow/04-CONTEXT.md`
- Current kernel requirements/state: `.planning/REQUIREMENTS.md`, `.planning/STATE.md`
- Roadmap split: `.planning/ROADMAP.md`

Relevant V1 constraints that should shape the plan:

- Telegram-first operator experience.
- Postgres-backed workflow artifacts remain the source of truth.
- Meaningful outbound writes stay approval-gated.
- No scope creep into a dashboard or generic workflow builder.

## What Already Exists

### The kernel already covers most of the hard orchestration semantics

- `packages/orchestration/src/helm_orchestration/workflow_service.py` already persists run creation, step transitions, validation artifacts, approval checkpoints, revision requests, sync manifests, sync execution, replay lineage, and final-summary assembly.
- A `schedule_proposal` artifact automatically creates an `await_schedule_approval` checkpoint before `apply_schedule`.
- Approval decisions already target a concrete proposal artifact id and can approve, reject, or request revision.
- Revision requests already create a new proposal attempt in the same run and preserve supersession lineage.
- Approved proposals already pre-materialize durable sync rows before execution begins.

This means `DEMO-04` and much of `DEMO-05` are implemented structurally already. Phase 4 is mostly about making the representative flow real and proving it end to end rather than inventing new kernel semantics.

### The representative workflow shell already exists but is still a demo stub

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` already registers `weekly_scheduling` specialist steps.
- `_build_task_agent_input` and `_build_calendar_agent_input` already map persisted raw request and normalized-task artifacts into typed specialist input schemas.
- `_run_task_agent` and `_run_calendar_agent` are still hard-coded placeholder handlers with fake tasks, fake blocks, and fixed constraints.

This is the main implementation gap for `DEMO-01` and the realism part of `DEMO-06`.

### Operator surfaces already exist and should be reused

- API routes already support create, detail, proposal versions, approve, reject, request revision, retry, and terminate.
- Telegram already supports `/workflow_start`, `/workflow_recent`, `/workflow_needs_action`, `/approve`, `/reject`, `/request_revision`, `/workflow_versions`, and `/workflow_replay`.
- `WorkflowStatusService` already projects approval state, proposal-version history, effect summaries, sync status, and final lineage in a shared read model.

Phase 4 should extend these surfaces, not create a second demo-specific control path.

## Contract Decisions Already Implied By The Code

### 1. Proposal approval is already artifact-version specific

The system requires approval actions to name the exact proposal artifact id. That is not optional now. Any Telegram or API UX for the representative flow must keep the operator anchored to the current actionable artifact version.

Planning implication:

- Do not design “approve latest” semantics.
- Keep proposal artifact ids visible enough in Telegram to act safely.

### 2. Revision already means “regenerate the schedule proposal”, not “restart the run”

`_request_revision_after_approval()` resumes the proposal-producing step and persists a `revision_request` artifact tied to the rejected proposal version. `_artifact_lineage_kwargs()` only marks a new schedule proposal as superseding the prior one when the latest revision request targets that prior proposal and the same producer step creates the new version.

Planning implication:

- The revised proposal path must continue to use the calendar proposal step.
- If task normalization must change after feedback, that would be a new scope decision, not the default Phase 4 path.

### 3. Approved downstream writes are derived only from `time_blocks`

`_build_approved_sync_items()` creates task upserts by deduping task titles from proposal `time_blocks`, then creates calendar upserts from each block. `proposed_changes` and warnings are display-only today.

Planning implication:

- The representative proposal must be honest about what `time_blocks` mean, because they are the source of outbound writes.
- If the desired workflow needs carry-forward or unscheduled items to affect downstream behavior, that requires a schema change. Today unscheduled work can only live in summary text or warnings.

### 4. The completion lineage contract is only partially populated

`build_final_summary_artifact()` currently links raw request, normalized/schedule artifacts, and validation artifact ids, but it does not populate approval decision linkage or downstream sync references even though the `WorkflowSummaryArtifact` schema supports them.

Planning implication:

- `DEMO-06` is not satisfied by existing “run completed” status alone.
- Phase 4 needs explicit work to produce a real final summary artifact for the representative flow with approval and sync linkage populated.

### 5. Telegram start currently points at the wrong workflow

`apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` still starts `workflow_type="weekly_digest"` at `normalize_request`, while the worker handlers are registered for `workflow_type="weekly_scheduling"` with `dispatch_task_agent` and `dispatch_calendar_agent`.

Planning implication:

- Fixing the start contract is the first concrete Phase 4 task.
- Until this is corrected, `DEMO-01` is blocked even though the lower-level kernel exists.

## Integration Gaps To Plan Around

### Request capture gap

The context says the request should be a structured brief: natural-language planning request plus inline task list plus explicit constraints. The current Telegram command only passes one free-text string and `chat_id` metadata.

Questions the plan must settle:

- Will `/workflow_start` parse a single compact message format into `metadata`, or will there be a weekly-scheduling-specific command?
- Which fields become durable request metadata versus remaining only in `request_text`?
- What is the minimum structured contract for tasks, protected time, deadlines, priorities, and no-meeting windows?

Recommended answer for planning:

- Keep one Telegram-first text command.
- Parse the message into stable metadata fields plus preserved original text.
- Avoid a conversational multi-turn form in Phase 4.

### Normalization realism gap

The task-agent step currently ignores the user request and emits fixed tasks. Phase 4 needs a real representative transformation from raw request to normalized task artifacts.

The plan should decide:

- whether Phase 4 uses deterministic parsing plus light normalization, or an LLM-backed `TaskAgent` implementation behind the existing typed schema.
- how ambiguity warnings are generated without blocking usable requests.

Given the repo constraints, the safer planning default is:

- deterministic extraction for the small supported input surface.
- warnings for omitted estimates/priority/ambiguity.
- no attempt to infer broad backlog state from elsewhere.

### Proposal realism gap

The calendar-agent step currently emits fixed blocks and fixed constraints. Phase 4 needs the generated proposal to reflect:

- requested tasks,
- explicit constraints,
- unscheduled/carry-forward items,
- rationale,
- assumptions/warnings,
- downstream change preview.

The current `ScheduleProposalArtifact` schema only has:

- `proposal_summary`
- `calendar_id`
- `time_blocks`
- `proposed_changes`
- `warnings`

Planning implication:

- Decide whether “unscheduled/carry-forward” and “rationale” can fit into `proposal_summary`/`warnings` for V1, or whether the proposal schema should be extended now.
- If those concepts matter to acceptance criteria, it is better to extend the schema in Phase 4 than to hide them in unstructured text.

### Completion summary gap

The phase context expects a completion summary emphasizing what was scheduled, what synced, and what still needs attention. Existing status projection can show sync counts and proposal versions, but there is no representative workflow-specific final summary artifact with that operator-facing summary yet.

Planning implication:

- Treat completion summary generation as first-class Phase 4 work, not a polish task.
- The summary should be built from persisted proposal, approval, and sync rows so it remains restart-safe and inspectable.

## Reusable Assets

These should reduce planning risk and keep the phase focused:

- `WorkflowResumeService` already gives restart-safe progression across runnable steps.
- Approval/revision/sync replay APIs and Telegram commands already exist and should be exercised by the representative workflow instead of recreated.
- `WorkflowStatusService` already projects proposal version history, approval checkpoints, sync counts, and safe next actions.
- Unit tests already cover kernel guarantees for approval checkpoints, proposal supersession, sync manifest idempotency, deterministic sync order, replay lineage, and status projection.

## Verification Risks

### Risk 1: solving only the happy path

The repository already has strong kernel tests, but Phase 4 can still fail if it only proves one happy-path demo request while leaving Telegram start, revision feedback, and final summary incomplete.

### Risk 2: request parsing drifting away from durable artifacts

If Telegram parsing logic becomes the only place that understands the request structure, API-created runs and stored raw requests will diverge. The parsing/normalization boundary needs one durable contract.

### Risk 3: proposal display and sync semantics diverging

Because outbound writes are derived from `time_blocks`, the operator-visible proposal summary must accurately represent those blocks. A compact Telegram summary cannot omit important scheduled or unscheduled implications.

### Risk 4: final summary remains underlinked

If the run completes without a populated final summary artifact referencing approval and sync lineage, `DEMO-06` remains only partially met.

## Recommended Plan Split

The roadmap already expects two plans. That split is correct.

### Plan 04-01: Implement the real representative weekly scheduling flow

Scope:

- Fix Telegram/API run creation to start the `weekly_scheduling` workflow at the correct first step.
- Define and implement the minimal structured weekly-request contract.
- Replace hard-coded task/calendar specialist handlers with representative request-driven logic.
- Ensure proposal output supports the required approval/revision experience, including visible carry-forward or assumptions.
- Keep all behavior on the shared kernel and shared status projection.

Primary requirement focus:

- `DEMO-01`
- `DEMO-04`
- `DEMO-05`

### Plan 04-02: Complete lineage, completion summary, and representative-flow verification

Scope:

- Populate a real final summary artifact for the representative flow, including approval decision linkage and downstream sync references/status.
- Verify end-to-end behavior across create, proposal, approval, revision, sync execution, restart-safe resume, and completion read models.
- Tighten Telegram/API operator summaries where they are insufficient for the representative workflow.

Primary requirement focus:

- `DEMO-06`
- verification depth for `DEMO-04` and `DEMO-05`

## Validation Architecture

This phase should produce a validation strategy artifact because acceptance depends on cross-boundary behavior rather than one module in isolation.

Recommended artifact:

- `.planning/phases/04-representative-scheduling-workflow/04-VALIDATION.md`

It should define at least these test layers:

- Contract tests for request parsing into durable raw-request metadata and specialist inputs.
- Orchestration tests for weekly-scheduling happy path, approval pause before any sync write, revision creating a new proposal version, and final-summary artifact linkage.
- Status-projection tests proving Telegram/API views show the latest actionable proposal, version history, sync counts, and completion summary correctly.
- Recovery tests proving restart-safe resume before approval, after revision, and during `apply_schedule`.

Minimum end-to-end scenarios to require in planning:

- Create run from Telegram-style weekly request with multiple tasks and explicit constraints.
- Generate proposal, pause for approval, then approve and execute downstream writes.
- Generate proposal, request revision with natural-language feedback, then approve the revised proposal.
- Complete run and verify lineage from raw request to final summary includes approved proposal version and sync record references.

## What The Planner Should Decide Up Front

- The exact Telegram message format for a structured weekly request.
- Whether proposal schema needs explicit fields for carry-forward/rationale instead of burying them in summary text.
- Where parsing lives so Telegram and API create paths share one durable request contract.
- How the representative task/calendar handlers stay deterministic and testable without introducing product breadth beyond the weekly demo.
- What exact final summary payload is needed to call `DEMO-06` complete.

## Bottom Line

Phase 4 does not need a new orchestration system. It needs to connect the already-built kernel to a real `weekly_scheduling` request contract, replace the placeholder specialist logic with representative transformations, and finish the final-summary lineage so the workflow is credibly end to end.