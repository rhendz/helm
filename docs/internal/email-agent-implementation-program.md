# Email Agent Implementation Program

Primary sources:
- `docs/internal/helm-v1.md`
- `/Users/ankush/Downloads/email-agent-system-definition.md`
- `docs/internal/email-agent-blocked-slices-and-decisions.md`

This document translates the Email Agent System Definition into an executable implementation program for the current Helm repository. It is intended to be a living manager document: prioritize foundational work, isolate ambiguity, and keep adjacent work moving when one path is blocked.

Current blocker/decision artifact:
- [email-agent-blocked-slices-and-decisions.md](/Users/ankush/git/helm/docs/internal/email-agent-blocked-slices-and-decisions.md)

## Architectural Context

The Email Agent sits inside the Helm V1 architecture as the email-domain specialist.

Boundaries in this repository:
- `packages/connectors`: Gmail change detection, normalization, message fetch.
- `packages/storage`: Email operational tables, artifact tables, repositories, migrations.
- `packages/agents`: standalone email-domain business logic, runtime ports, and repo-local adapters.
- `packages/orchestration`: non-email shared workflow logic only; Email Agent no longer depends on Helm orchestration wrappers.
- `apps/worker`: scheduled scans, queue consumers, replay/recovery jobs.
- `apps/api`: structured operator and debug endpoints for surfaced items, thread inspection, seed/reprocess triggers, and approval/send actions.
- `apps/telegram-bot`: Telegram-first UX for approvals, reminders, review-needed items, and action lists.

Required architectural distinctions from the system definition:
- `EmailThread` is the main aggregate.
- `EmailMessage` is the replayable atomic record.
- business state is distinct from execution state.
- `ActionProposal` is distinct from `Draft`.
- final outbound `EmailMessage` is distinct from the original `Draft`.
- artifacts/traces are separate from operational truth.
- config is separate from policy.
- policy is separate from rubrics.
- Helm coordination artifacts remain Helm-owned, not Email Agent-owned.

## Current Repository State

Implemented baseline:
- Gmail normalization and polling scaffold exists.
- Email triage orchestration scaffold exists.
- Generic `email_messages`, `email_threads`, `action_items`, `draft_replies`, `digest_items`, and `agent_runs` persistence exists.
- Basic worker polling job exists.
- Basic API draft/action listing exists.

Major gaps against the Email Agent System Definition:
- current storage model is generic and does not represent the Email Agent aggregate and artifacts cleanly.
- no first-class business-state enum or transition model exists.
- no `ActionProposal` object exists.
- current draft model is generic and does not model approval lineage or final sent-message linkage.
- no `ScheduledThreadTask` object exists for reminders/follow-ups.
- visible labels, resurfacing source, action reason, and confidence bands are not durably represented on thread state.
- no classification artifact or draft reasoning artifact persistence exists.
- metadata-first seed planning and deep-seed queue scaffolding exist, but deeper seed quality remains limited.
- stale follow-up scan exists with weekday-only business-day scheduling.
- manual approval-before-send execution and worker-owned retry/recovery exist.
- API and Telegram surfaces are still generic artifact views, not email-domain views.

Implementation stance:
- the current email-agent implementation should be treated as a bootstrap scaffold, not a design constraint.
- when the existing generic models or workflow shortcuts conflict with the system definition, replace them instead of layering more behavior onto the wrong abstraction.
- prefer bounded migration work over compatibility shims unless a shim is required to preserve repository stability during the transition.

Decoupling status:
- `packages/agents/src/email_agent` now defines the Email Agent core boundary.
- Helm app layers call Email Agent through explicit ports plus the Helm-backed adapter in `helm_runtime.email_agent`.
- legacy Helm compatibility wrappers for email triage and scheduling have been removed.

## Priority Order

Build first:
1. operational data model alignment
2. business-state transition scaffolding
3. message-to-thread incremental ingestion correctness
4. action proposal and draft lineage separation
5. scheduled reminder/follow-up scaffolding
6. structured API and Telegram retrieval surfaces
7. metadata-first seed and rebuild pipeline
8. send-approval execution path and failure protection
9. artifact trace enrichment and evaluation scaffolding

Build next:
1. selective deep-seed heuristics
2. richer classification scaffolding
3. draft generation scaffolding with reasoning artifacts
4. reminder/follow-up user commands
5. scheduled inbox reconciliation sweep

Build later:
1. prompt/rubric maturation once companion docs exist
2. advanced confidence calibration
3. contact artifact enrichment beyond lightweight fragments
4. Helm-to-email coordination artifacts

Refactor principle:
- replacement work that restores the spec boundary is higher priority than extending the existing generic email scaffold.

## Ready To Build

These items are implementable now from the current spec without waiting for companion docs.

### P0 Foundations

1. Email operational schema realignment
- Boundary: `packages/storage`
- Objective: represent `EmailThread`, `EmailMessage`, `ActionProposal`, `Draft`, `ScheduledThreadTask`, and `EmailAgentConfig` as first-class persistence objects.
- Notes: current generic tables can be migrated or superseded, but the end state must preserve thread aggregate semantics and lineage pointers.

2. Business-state enum and transition rules
- Boundary: `packages/storage`, `packages/agents`, `packages/orchestration`
- Objective: encode `uninitialized`, `waiting_on_user`, `waiting_on_other_party`, `needs_review`, `resolved` plus `resurfacing_source`, `action_reason`, `confidence_band`.
- Notes: keep execution state separate from thread business state.

3. Incremental thread update pipeline
- Boundary: `packages/orchestration`, `packages/storage`, `packages/connectors`
- Objective: convert a changed message into deterministic thread updates, message linkage updates, labels, and derived surfacing metadata.
- Notes: process the changed message first; pull thread history only when required.

4. Visible label persistence
- Boundary: `packages/storage`, `packages/agents`
- Objective: durably store visible labels `Action`, `Urgent`, `NeedsReview` on the thread aggregate with derivation paths that can be refreshed after reprocessing or human override.

5. `ActionProposal` scaffolding
- Boundary: `packages/storage`, `packages/agents`, `packages/orchestration`
- Objective: persist next-step recommendations independently from drafts.
- Notes: support proposal lifecycle `proposed`, `accepted`, `rejected`, `expired`.

6. Draft lineage model
- Boundary: `packages/storage`, `packages/agents`
- Objective: represent agent draft, approval state, final outbound sent message linkage, and source action proposal linkage.
- Notes: preserve comparison between original draft and final sent message.

7. `ScheduledThreadTask` scaffolding
- Boundary: `packages/storage`, `packages/worker`, `packages/orchestration`
- Objective: model reminders and follow-up tasks with neutral scheduling semantics.
- Notes: include `task_type`, `created_by`, `due_at`, `status`, `reason`.

### P1 Retrieval and control surfaces

8. Email-thread API retrieval shapes
- Boundary: `apps/api`
- Objective: expose structured thread, proposal, draft, and scheduled-task objects instead of generic list endpoints.
- Notes: keep provider ids and internal ids stable and explicit.

9. Manual seed and targeted reprocess endpoints
- Boundary: `apps/api`, `packages/orchestration`, `apps/worker`
- Objective: expose manual inbox initialization/rebuild and targeted thread reprocessing triggers.
- Notes: support dry-run/reporting where practical.

10. Stale follow-up scan job
- Boundary: `apps/worker`, `packages/orchestration`, `packages/storage`
- Objective: resurface threads after the global default 3-business-day follow-up window while preserving `waiting_on_other_party` business state.

11. Reminder-due execution path
- Boundary: `apps/worker`, `packages/orchestration`, `packages/storage`
- Objective: process due `ScheduledThreadTask` records and update surfacing metadata without changing business state unless explicitly required.

12. Human override refresh path
- Boundary: `packages/orchestration`, `apps/api`, `apps/telegram-bot`
- Objective: when the user marks done, acknowledges, snoozes, or resolves review, recompute derived outputs using the human decision as source of truth.

### P2 Artifact and reliability scaffolding

13. Classification artifact persistence
- Boundary: `packages/storage`, `packages/orchestration`
- Objective: persist classification decision trace separately from thread operational truth.

14. Draft reasoning artifact persistence
- Boundary: `packages/storage`, `packages/agents`
- Objective: persist tone rationale, assumptions, confidence, and context lineage separately from draft operational rows.

15. Metadata-first seed pipeline scaffold
- Boundary: `packages/connectors`, `packages/orchestration`, `apps/worker`
- Objective: create pass-1 metadata triage outputs `deep_seed`, `light_seed_only`, `do_not_surface` and queue deep seed work.

16. Safe send execution scaffold
- Boundary: `apps/api`, `packages/orchestration`, `packages/connectors`, `packages/storage`
- Objective: enforce approval-before-send, persist final outbound `EmailMessage`, and preserve draft state on send failure.

## Needs Clarification

These areas should not be implemented beyond scaffolding until a companion document or decision exists.

1. Email labeling workflow/rubric
- Unclear: exact decision workflow for `should_surface`, `Action`, `Urgent`, `NeedsReview`, confidence production, and initial-vs-incremental behavior.
- Why it matters: blocks high-quality classification implementation and acceptance tests.
- Safe now: build persistence, transition plumbing, and placeholder classifier interfaces.

2. Email drafting workflow/rubric
- Unclear: when to auto-draft versus propose action only, tone/style selection, refinement behavior, and how Helm-injected constraints are balanced.
- Why it matters: blocks serious draft quality work.
- Safe now: build draft lifecycle, approval metadata, lineage, and reasoning artifact shape.

3. `EmailAgentPolicy.md`
- Unclear: broad operating guidance for surfacing philosophy, ambiguity handling, and drafting philosophy.
- Why it matters: blocks non-trivial behavioral decisions that should not be hard-coded from guesswork.
- Safe now: keep conservative heuristics and isolate policy-dependent logic behind interfaces.

4. Email agent config storage location
- Unclear: whether `EmailAgentConfig` should live in Postgres as a small table, a JSON config object, or another config store in this repo.
- Why it matters: affects cursor persistence and feature-toggle wiring.
- Safe now: define repository contract and object shape before locking storage implementation.

5. Artifact store choice for document-oriented traces
- Unclear: whether v1 keeps artifacts in Postgres JSON columns, separate tables, or a document store.
- Why it matters: affects schema design for classification and draft reasoning traces.
- Safe now: define explicit artifact schema contracts and keep storage implementation swappable.

6. Business-day calculation contract
- Unclear: exact calendar semantics for the 3-business-day follow-up rule beyond weekday-only logic, including future holiday support.
- Why it matters: affects follow-up due logic and tests.
- Safe now: wire a business-day service interface with a default weekday-only implementation pending refinement.

7. Approval/send transport contract
- Unclear: exact provider send path, duplicate-send protection contract, and send-attempt logging shape.
- Why it matters: blocks production-grade outbound execution.
- Safe now: implement approval state machine and send-attempt persistence scaffold.

## Deferred By Design

These should remain explicitly out of scope for the current implementation push unless the spec changes.

1. learned memory architecture
2. advanced confidence calibration from historical corrections
3. rich capability catalog on top of the API
4. richer cross-agent contact graph and persona synthesis
5. Helm-owned coordination trace model
6. nuanced capability composition beyond immediate API needs
7. broad provider-side inbox reorganization
8. autonomous send authority without user approval

## Sequenced Execution Waves

### Wave 1
- storage schema realignment
- repository contracts for thread/message/proposal/draft/scheduled task
- business-state enums and transition helpers
- migration and repository tests

### Wave 2
- incremental update orchestration refactor around `EmailThread`
- visible label persistence
- action proposal persistence
- classification artifact write path

### Wave 3
- draft lineage and approval metadata
- final outbound message linkage
- stale follow-up scan
- reminder task execution path

### Wave 4
- manual seed/rebuild endpoint and queue visibility
- metadata-first seed pass and deep-seed queue scaffold
- targeted reprocess endpoint and dry-run reporting

### Wave 5
- Telegram review/approval surfaces bound to email-domain objects
- send retry/recovery quality hardening and operator ergonomics
- richer artifact trace endpoints and runbook updates

## Architectural Pressure Notes

1. The spec assumes first-class email-domain objects, but the current codebase still uses generic `ActionItem` and `DraftReply` tables. Pressure is highest in `packages/storage`.
2. The state model is more mature than the current workflow graph. We need a transition layer before classification quality work is meaningful.
3. Reminder and stale follow-up are first-class resurfacing reasons in the spec, but the current system has no neutral scheduled-task object.
4. The spec clearly separates proposal, draft, and final outbound message. Current persistence collapses this distinction.
5. Cold start requires metadata triage before deep processing. Current connector/orchestration code only supports message-level polling.
6. The API contract is currently artifact-oriented and generic. The spec needs email-domain retrieval and control objects.
7. Artifact persistence is underspecified at the storage level even though artifacts are central to evaluation and replay.
8. The approval/send boundary is explicit in the spec, but the codebase has no send attempt model or outbound email persistence path.

## Suggested Companion Docs

Priority order:
1. `Email Labeling Workflow / Rubric`
- Highest leverage because it gates real classification behavior, confidence routing, and test expectations.

2. `Email Drafting Workflow / Rubric`
- Needed after proposal/draft lifecycle scaffolding exists so draft quality work has a defined target.

3. `EmailAgentPolicy.md`
- Needed to keep broad behavioral guidance out of code and prompts once the execution path expands.

4. `EmailAgentConfig` decision note
- Needed to lock storage/ownership for cursor, follow-up defaults, and approval flags.

## Candidate Ticket Groups

### Storage + Persistence
- Email operational schema realignment
- repositories for thread/message/proposal/draft/scheduled task/config
- artifact persistence tables/contracts
- migration tests and idempotency checks

### Orchestration + Agent Logic
- business-state transition helpers
- incremental update pipeline refactor
- classification artifact writes
- draft generation scaffold
- human override refresh path

### Worker + Scheduling
- stale follow-up scan
- reminder-due processing
- metadata-first seed pass queueing
- scheduled inbox sweep hardening

### API + Telegram
- structured email thread endpoints
- manual rebuild/reprocess triggers
- approval/send endpoints
- Telegram review/approval/reminder surfaces

### Clarification / Design Review
- labeling rubric authoring
- drafting rubric authoring
- policy document authoring
- artifact store choice
- config storage decision

## Linear Backlog Snapshot

Implementation-ready:
- `HELM-44` Replace generic email persistence with spec-aligned `EmailThread` aggregate schema
- `HELM-45` Implement `EmailThread` business-state transitions and surfacing metadata model
- `HELM-46` Refactor incremental email processing around the `EmailThread` aggregate
- `HELM-47` Persist visible labels and classification artifacts separately from thread operational truth
- `HELM-48` Implement `ActionProposal` and `Draft` lineage with approval metadata
- `HELM-49` Add `ScheduledThreadTask` model and stale follow-up/reminder execution scaffolding
- `HELM-50` Add email-domain API endpoints for threads, proposals, drafts, and manual reprocessing
- `HELM-51` Build metadata-first inbox seed and selective deep-seed queue scaffold
- `HELM-52` Add safe send execution scaffold with final outbound `EmailMessage` persistence

Clarification / companion-doc work:
- `HELM-53` Author Email labeling workflow and confidence routing rubric
- `HELM-54` Author Email drafting workflow and refinement rubric
- `HELM-55` Author `EmailAgentPolicy.md` for surfacing and drafting behavior
- `HELM-56` Decide `EmailAgentConfig` storage contract and ownership
- `HELM-57` Decide artifact persistence shape for classification and draft reasoning traces
- `HELM-58` Define business-day follow-up and approval-send contract details

Current execution recommendation:
1. Start `HELM-44`
2. Run `HELM-45` in parallel once the replacement schema shape is stable
3. Keep `HELM-53`, `HELM-56`, and `HELM-57` moving in parallel to reduce downstream blocking

## Immediate Next Moves

1. Cut foundational Linear issues for schema, state model, incremental updates, scheduled tasks, and API surfaces.
2. Cut separate clarification/design-review issues for rubric, policy, artifact store, config storage, and send contract.
3. Keep implementation tickets small enough to land independently inside the repository’s parallel boundaries.
4. Re-run this document after each ticket batch so sequencing stays aligned to the architecture instead of drifting toward the current scaffold.
