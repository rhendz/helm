# Phase 4: Representative Scheduling Workflow - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the kernel end to end with one fixed weekly scheduling workflow: a user submits a weekly planning request, Helm normalizes the work, produces a schedule proposal, pauses for approval or revision, and after approval executes downstream task and calendar writes with durable lineage through completion.

</domain>

<decisions>
## Implementation Decisions

### Request contract
- The representative flow should start primarily from a Telegram command.
- The request should be a structured brief: natural-language planning request plus inline task list and a small set of explicit constraints.
- The task list should be included directly in the request rather than inferred entirely from broad goals or pulled mainly from an existing backlog.
- The first supported constraints should stay simple and explicit: protected time, deadlines, priorities, and basic no-meeting windows.
- If the request is incomplete but still usable, Helm should continue and surface assumptions or ambiguity warnings instead of blocking for clarification before proposal generation.

### Schedule proposal shape
- The default Telegram proposal should be a compact summary, not a dense block-by-block timeline.
- The proposal should show the main scheduled blocks, the most important honored constraints, and a concise list of planned downstream changes.
- If not every requested task fits, the proposal must include an explicit unscheduled or carry-forward section rather than forcing everything into the week or dropping items quietly.
- The proposal should include a short rationale for the major scheduling choices.
- Assumptions and ambiguity warnings should appear in a separate visible section instead of being hidden or mixed into the default block list.

### Approval and revision experience
- The default approval checkpoint should optimize for decision speed in Telegram while still showing the key facts needed to approve, reject, or request revision.
- Revision feedback should be natural-language first, with optional lightweight hints allowed when useful.
- Rejecting the proposal should end the run cleanly with no downstream writes, rather than prompting an immediate alternate proposal by default.
- Proposal version history should remain available on demand, but the latest version should stay primary in the default operator view.

### Completion summary
- A successful representative run means the proposal was approved and the corresponding task and calendar writes completed.
- The default completion summary should emphasize the outcome first: what was scheduled, what was synced, and what still needs attention.
- The default completion summary should show counts plus a few highlights rather than listing every downstream write inline.
- Unscheduled or carry-forward items should remain visible in the final summary so the completed run stays honest about what did not fit.
- Deeper lineage and downstream object details should be inspectable on demand rather than dominating the default Telegram completion message.

### Claude's Discretion
- Exact Telegram command naming, message formatting, and API payload shape as long as the Telegram-first request contract stays intact.
- Exact field names for request metadata and specialist input payloads as long as the structured-brief semantics remain clear.
- How much compact detail fits in the default proposal and completion summaries before linking or routing users to richer detail views.
- The exact representation of optional revision hints, provided plain-language feedback remains the default and fully supported path.

</decisions>

<specifics>
## Specific Ideas

- The representative request should feel like: "Plan my week. Tasks: finish roadmap draft, prep two interviews, clear inbox. Constraints: protect deep work mornings, keep Friday afternoon open, deadline Wednesday for roadmap."
- The proposal should feel honest rather than over-optimized: scheduled blocks, key assumptions, and explicit carry-forward items if the week is too full.
- Telegram should remain the fast decision surface; richer inspection stays available through existing API and workflow-detail paths.
- Revision feedback should work well with phrases like "keep Friday afternoon open" and "move interview prep earlier in the week," with optional hints layered on top later.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`: already defines the representative `weekly_scheduling` specialist steps and stub task/calendar handlers, so Phase 4 can harden and replace those placeholders instead of inventing a new flow.
- `packages/orchestration/src/helm_orchestration/schemas.py`: already provides raw request, normalized task, schedule proposal, approval, and sync schema contracts that fit this phase directly.
- `apps/api/src/helm_api/routers/workflow_runs.py`: already exposes create, approval, rejection, revision, retry, terminate, and proposal-version routes for workflow runs.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`: already provides Telegram start, recent, needs-action, replay, and proposal-version views that can become the primary operator surface for this demo.

### Established Patterns
- Telegram is the concise primary operator surface, while API endpoints can carry richer inspection detail.
- Approval checkpoints are latest-version first and target a concrete proposal artifact id.
- Revision creates a new proposal version inside the same workflow run rather than restarting from scratch.
- Operator-facing summaries should stay compact and action-oriented, with deeper lineage available on demand.

### Integration Points
- The representative workflow should continue to use `workflow_type="weekly_scheduling"` and the existing workflow run create/resume path.
- The request contract can flow through the existing raw request artifact metadata into `TaskAgentInput` and `CalendarAgentInput`.
- Proposal, approval, revision, replay, and completion reporting should extend the existing workflow status projection rather than create a separate demo-only read path.

</code_context>

<deferred>
## Deferred Ideas

- Using a pre-existing backlog as the primary source for weekly planning rather than inline task entry.
- Rich calendar rule systems beyond simple explicit constraints.
- Deep default Telegram inspection of every schedule block or every downstream write.
- Structured revision forms or categories that replace plain-language feedback.

</deferred>

---
*Phase: 04-representative-scheduling-workflow*
*Context gathered: 2026-03-13*
