# Phase 2: Specialist Dispatch And Approval Semantics - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Add typed `TaskAgent` and `CalendarAgent` dispatch, durable approval checkpoints, revision-driven proposal versioning, and safe resume behavior inside the workflow kernel. This phase defines specialist invocation and operator decision semantics, but it does not yet execute downstream task-system or calendar writes.

</domain>

<decisions>
## Implementation Decisions

### Specialist contract
- `TaskAgent` should receive a hybrid envelope: stable workflow and runtime metadata, the raw user request, and any already-known constraints or resolved context.
- Helm should not fully over-normalize natural user input before specialist dispatch; domain inference should still happen inside the specialist.
- `CalendarAgent` should run primarily from validated task artifacts and explicit scheduling constraints, with raw or source context passed only as supplemental input when needed.
- Specialist outputs may include warnings and ambiguity flags, but the workflow only advances when the output still satisfies the current step schema.
- Persisted invocation records should include input references, output references, timing, and result status as the core durable contract.

### Approval flow
- Telegram should present approval checkpoints as a compact proposal summary with explicit actions.
- The core approval decision model is approve, reject, and request revision.
- Snooze or delay is desirable as a checkpoint control action, but it should not replace the core approval decisions.
- Revision feedback should be natural-language first, with optional structured hints allowed later rather than required from the start.
- The default checkpoint view should show the proposal summary, why Helm is paused, and the immediate effects of approval, rejection, or revision.

### Revision model
- A revision request should create a new proposal artifact version inside the same workflow run rather than overwriting the current proposal or starting a new child run.
- The latest proposal version should be the default operator view, while older versions remain inspectable on demand.
- Revision should resume at the proposal-producing specialist step rather than restarting the workflow from the beginning.
- Each revised proposal should preserve the original revision feedback and an explicit superseded link to the prior proposal version.

### Step progression
- The workflow should auto-advance through specialist and validation steps as long as artifacts are schema-valid and no approval checkpoint or blocking failure has been reached.
- Warnings on valid artifacts should be persisted and surfaced in status and approval views, but should not create a separate checkpoint in Phase 2.
- In the representative scheduling flow, the first explicit operator pause should happen after the schedule proposal is produced and before any downstream writes.
- Before an approval checkpoint exists, operator intervention should stay narrow: status visibility plus explicit retry or terminate actions.

### Claude's Discretion
- Exact schema and class names for specialist invocation payloads and approval records.
- Whether snooze or delay lands in Phase 2 proper or is deferred as a small follow-on if the planning breakdown reveals it is not essential to the phase goals.
- How API and Telegram expose on-demand access to older proposal versions as long as the default view stays latest-first.

</decisions>

<specifics>
## Specific Ideas

- The kernel should supply a stable dispatch contract without becoming a heavy interpretation layer for natural-language requests.
- Telegram remains the low-friction decision surface, so revision needs to work well with plain-text feedback.
- Approval views should optimize for operational clarity: what Helm proposes, why it paused, and what each action will do next.
- Revision is not the same as retry; revised proposals should be visibly new versions with preserved lineage.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/orchestration/src/helm_orchestration/workflow_service.py`: already owns durable step transitions, validation gating, retry, terminate, and final-summary helpers that Phase 2 can extend with specialist invocation and approval checkpoints.
- `packages/orchestration/src/helm_orchestration/resume_service.py`: already defines storage-backed workflow resume behavior that can become the dispatch point for typed specialist handlers.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`: already provides thin workflow start, status, retry, and terminate command patterns that approval and revision commands should align with.
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py`: existing approval-style command provides a lightweight operator-action pattern worth either reusing or intentionally replacing.
- `apps/api/src/helm_api/services/workflow_status_service.py` and `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`: shared workflow read-model pattern can carry approval state and proposal-version visibility without duplicating rules.
- `packages/storage/src/helm_storage/repositories/workflow_runs.py`, `workflow_steps.py`, `workflow_artifacts.py`, and `workflow_events.py`: existing durable repositories already support the step, artifact, and event lineage this phase needs.

### Established Patterns
- App layer orchestrates while reusable workflow behavior lives in package boundaries.
- Workflow state, artifacts, and operator actions are persisted in Postgres-first storage rather than transient memory.
- Validation warnings can exist without blocking progress, but invalid outputs must stop the workflow durably.
- Telegram is concise and action-oriented by default, while API surfaces can carry deeper inspection detail.

### Integration Points
- Specialist handler registration should plug into the workflow resume path rather than introduce a parallel execution loop.
- Approval checkpoints should feed the existing workflow status read models so API and Telegram stay aligned on paused-state semantics.
- Proposal versioning should extend the artifact lineage model created in Phase 1 instead of inventing a separate revision store.

</code_context>

<deferred>
## Deferred Ideas

- Rich mid-run operator controls beyond status, retry, and terminate.
- Preset revision categories or fully structured revision forms.
- A deeper warning taxonomy that distinguishes informational warnings from escalation-worthy warnings.

</deferred>

---
*Phase: 02-specialist-dispatch-and-approval-semantics*
*Context gathered: 2026-03-13*
