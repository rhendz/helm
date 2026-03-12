---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 03-04-PLAN.md
last_updated: "2026-03-12T23:06:23.066Z"
last_activity: 2026-03-12 — Completed phase 3 plan 04 shared workflow status projection for sync recovery semantics
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 11
  completed_plans: 10
  percent: 91
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-11)

**Core value:** Helm can execute multi-step, approval-gated workflows reliably enough that workflow state, artifacts, and side effects remain durable and inspectable across restarts and failures.
**Current focus:** Phase 3 - Adapter Writes And Recovery Guarantees

## Current Position

Phase: 3 of 4 (Adapter Writes And Recovery Guarantees)
Plan: 4 of 5 in current phase
Status: In progress
Last activity: 2026-03-12 — Completed phase 3 plan 04 shared workflow status projection for sync recovery semantics

Progress: [█████████░] 91%

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: 11 min
- Total execution time: 1.9 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | 30 min | 10 min |
| 2 | 3 | 30 min | 10 min |
| 3 | 4 | 56 min | 14 min |

**Recent Trend:**
- Last 5 plans: 6 min, 20 min, 17 min, 10 min, 9 min
- Trend: Stable

*Updated after each plan completion*
| Phase 01 P02 | 6 min | 3 tasks | 11 files |
| Phase 01 P03 | 12 min | 3 tasks | 11 files |
| Phase 02-specialist-dispatch-and-approval-semantics P01 | 6 min | 3 tasks | 15 files |
| Phase 02-specialist-dispatch-and-approval-semantics P02 | 9 | 3 tasks | 23 files |
| Phase 02-specialist-dispatch-and-approval-semantics P03 | 15 min | 3 tasks | 17 files |
| Phase 03 P01 | 20 min | 3 tasks | 11 files |
| Phase 03 P02 | 17 min | 3 tasks | 14 files |
| Phase 03 P03 | 10 min | 3 tasks | 11 files |
| Phase 03 P04 | 9 min | 3 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Initialization]: Focus v1 on the orchestration kernel rather than domain workflow expansion
- [Initialization]: Use a fixed weekly scheduling workflow to prove the kernel end to end
- [Initialization]: Keep approval mandatory before downstream create, update, or delete side effects
- [2026-03-13]: Keep durable workflow state in dedicated `workflow_*` tables instead of extending legacy email-specific persistence.
- [2026-03-13]: Freeze the final summary artifact contract early with nullable approval and downstream sync linkage fields.
- [Phase 01]: Model workflow artifacts and failures as explicit Pydantic schemas so storage payloads stay typed before specialist adapters exist.
- [Phase 01]: Treat validation failures as blocked runs that require an explicit retry or terminate action instead of implicit worker progression.
- [Phase 01]: Worker polling must skip runnable workflow runs until concrete step handlers are registered.
- [Phase 01]: API and Telegram workflow operator surfaces must share a single read-model service so paused-state and recovery semantics do not diverge.
- [Phase 01]: Operator clients should receive explicit retry and terminate actions from workflow read models instead of reconstructing recovery rules locally.
- [Phase 01]: Final workflow summary responses should always include nullable approval and downstream sync linkage keys before later phases populate them.
- [Phase 02-specialist-dispatch-and-approval-semantics]: Persist specialist execution in a dedicated workflow_specialist_invocations table so approval and operator views can query invocation lineage directly.
- [Phase 02-specialist-dispatch-and-approval-semantics]: Execute specialist steps inside WorkflowOrchestrationService so worker code only registers semantic dispatch entries and resumes durable state.
- [Phase 02-specialist-dispatch-and-approval-semantics]: Store schedule proposals as first-class workflow artifacts validated through the same kernel path as normalized task artifacts.
- [Phase 02-specialist-dispatch-and-approval-semantics]: Approval checkpoints live in a dedicated workflow_approval_checkpoints table linked to approval request and decision artifacts.
- [Phase 02-specialist-dispatch-and-approval-semantics]: Schedule proposals pause at an explicit await_schedule_approval step so approval waits stay distinct from validation and execution failures.
- [Phase 02-specialist-dispatch-and-approval-semantics]: API and Telegram approval actions must consume one shared checkpoint-aware workflow status projection and delegate all decision semantics to the kernel.
- [Phase 02-specialist-dispatch-and-approval-semantics]: Approval actions must target a concrete proposal artifact id so later revisions cannot change which version gets resolved.
- [Phase 02-specialist-dispatch-and-approval-semantics]: Revision requests persist as artifacts and the next schedule proposal supersedes the prior proposal within the same run.
- [Phase 03]: Approved proposal execution now materializes deterministic task and calendar sync records before any adapter call path runs.
- [Phase 03]: Sync identity is anchored to proposal artifact id, proposal version, target system, sync kind, and planned item key with relational uniqueness.
- [Phase 03]: Adapter protocols return normalized request, outcome, and reconciliation envelopes while orchestration retains ordering and retry policy.
- [Phase 03]: Sync retries and restarts rebuild remaining work from persisted sync records scoped to step lineage.
- [Phase 03]: Orchestration owns sync ordering, retryability, and reconciliation while connectors expose only upsert and reconcile contracts.
- [Phase 03]: Uncertain sync outcomes must reconcile durable identity before Helm issues another outbound write.
- [Phase 03]: Replay creates a new sync-row lineage generation for the same planned item so prior execution history stays queryable.
- [Phase 03]: Termination after partial success cancels remaining sync work and records partial counts instead of rewriting succeeded rows.
- [Phase 03]: Recovery classification lives on durable sync rows plus workflow events so app-layer projections do not infer semantics from free-form error text.
- [Phase 03]: Workflow status projection reads sync counts, recovery class, and replay lineage directly from workflow_sync_records so operator surfaces do not parse workflow events.
- [Phase 03]: Effect summaries stay compact and stable: total writes plus task/calendar counts before execution begins.
- [Phase 03]: Terminal partial-sync state takes precedence over stale adapter error text when projecting operator-facing recovery summaries.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 1 should choose a workflow schema vocabulary that does not duplicate existing email-specific artifact concepts unnecessarily.
- Phase 2 should validate how much LangGraph state Helm should own directly versus what remains inside graph persistence.

## Session Continuity

Last session: 2026-03-12T23:06:23.064Z
Stopped at: Completed 03-04-PLAN.md
Resume file: None
