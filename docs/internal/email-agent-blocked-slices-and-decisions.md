# Email Agent Blocked Slices And Decisions

Primary references:
- `/Users/ankush/Downloads/email-agent-system-definition.md`
- [email-agent-implementation-program.md](/Users/ankush/git/helm/docs/internal/email-agent-implementation-program.md)

This document records the Email Agent work that is blocked or not safe to continue, why it is blocked, and the implementation decisions that are already forced by current code pressure.

The goal is to make the next execution pass straightforward:
- finish the decisions that are still open
- convert open decisions into explicit ticket-unblocking inputs
- resume implementation without guessing through architecture

## Current State

Unblocked implementation slices were merged through:
- `HELM-46` incremental trigger families
- `HELM-48` draft lineage retrieval + Telegram draft inspection
- `HELM-49` scheduled task failure isolation
- `HELM-50` thread/proposal/draft/task/reprocess operator surfaces
- `HELM-51` metadata-first seed planning surface

What remains is not “no more work.”
What remains is “no more safe implementation without making decisions first.”

## Blocked / Not Safe Slice Register

### `HELM-52` Safe Send Execution Scaffold
- Status: blocked
- Why it is not safe:
  - outbound send contract is still underspecified
  - recipient selection and final outbound payload ownership are not defined tightly enough
  - duplicate-send protection and send-attempt persistence rules are still unclear
- What implementation this blocks:
  - provider send path
  - final outbound `EmailMessage` persistence
  - reliable `Draft.final_sent_message_id` population
  - approval-gated send endpoint and worker path
- Decision dependency:
  - `HELM-58`

### `HELM-53` Email Labeling Workflow / Confidence Routing Rubric
- Status: companion doc authored
- Why it is not safe:
  - current rule-based classifier is only scaffolding
  - more classification work would otherwise hard-code rubric decisions into application logic
- What implementation this blocks:
  - real `should_surface` logic
  - higher-quality label derivation
  - non-trivial confidence routing behavior
- Companion doc:
  - [Email-Labeling-Workflow-Rubric.md](/Users/ankush/git/helm/docs/internal/Email-Labeling-Workflow-Rubric.md)

### `HELM-54` Email Drafting Workflow / Refinement Rubric
- Status: companion doc authored
- Why it is not safe:
  - drafting quality work needs explicit rules for when to draft, when to propose-only, and how to refine
- What implementation this blocks:
  - richer drafting behavior
  - drafting quality evaluation
  - draft reasoning artifact semantics beyond scaffolding
- Companion doc:
  - [Email-Drafting-Workflow-Rubric.md](/Users/ankush/git/helm/docs/internal/Email-Drafting-Workflow-Rubric.md)

### `HELM-55` `EmailAgentPolicy.md`
- Status: companion doc authored
- Why it is not safe:
  - broad behavior choices should live in policy, not emerge from scattered code heuristics
- What implementation this blocks:
  - ambiguity-handling behavior
  - surfacing philosophy beyond narrow scaffolding
  - drafting philosophy beyond narrow scaffolding
- Companion doc:
  - [EmailAgentPolicy.md](/Users/ankush/git/helm/docs/internal/EmailAgentPolicy.md)

### `HELM-56` `EmailAgentConfig` Storage Contract
- Status: mostly decided
- Why this was previously blocking:
  - config ownership and persistence could have spread into ad hoc env vars or generic tables
- Current state:
  - enough evidence now exists to lock the storage contract for v1

### `HELM-57` Artifact Persistence Shape
- Status: partially decided
- Why it is not fully safe yet:
  - classification artifacts have a clear persistence shape now
  - draft reasoning artifacts do not yet have a dedicated table/contract beyond a reference field
- What implementation this still blocks:
  - real draft reasoning persistence
  - consistent artifact querying for draft-generation traces

### `HELM-58` Business-Day Follow-Up + Approval/Send Contract
- Status: mostly decided
- Why it is not fully safe yet:
  - follow-up timing and send retry semantics are now defined for v1
  - remaining work is implementing the contract, not inventing it
- What implementation this blocks:
  - `HELM-52`
  - any richer scheduling semantics beyond the simple default

## Decisions

These are the decisions that should now be treated as the baseline unless explicitly revised.

### Decision 1: `EmailAgentConfig` lives in Postgres and is Email Agent-owned
- Ticket: `HELM-56`
- Status: decided
- Decision:
  - `EmailAgentConfig` is stored in Postgres in `email_agent_configs`
  - ownership belongs to the Email Agent domain, not Helm-global config
  - v1 contract is a singleton config row
- Evidence in code:
  - [models.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/models.py)
  - [email_agent_config.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/repositories/email_agent_config.py)
- Current fields already supported:
  - `approval_required_before_send`
  - `default_follow_up_business_days`
  - `last_history_cursor`
- Implication:
  - `HELM-56` should stop blocking implementation

### Decision 2: Classification artifacts are first-class Postgres rows separate from operational truth
- Ticket: `HELM-57`
- Status: decided for transitional scaffolding
- Decision:
  - classification artifacts are stored in their own Postgres table
  - they are linked to thread/message ids
  - they are not the source of operational truth
- Evidence in code:
  - [models.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/models.py)
  - [classification_artifacts.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/repositories/classification_artifacts.py)
- Implication:
  - the classification-artifact portion of `HELM-57` is resolved
- Clarification:
  - the spec target is LLM/rubric-driven classification
  - the current implementation still contains rule-based classification scaffolding
  - current classification artifacts should be treated as transitional scaffolding, not the final reasoning contract

### Decision 3: Draft reasoning should follow the same separation model as classification artifacts
- Tickets: `HELM-54`, `HELM-57`
- Status: provisional
- Decision:
  - draft reasoning should be stored separately from `email_drafts`
  - `email_drafts` should keep only a reference to the reasoning artifact
  - v1 should prefer Postgres-backed document-style artifact rows over embedding reasoning blobs directly into operational draft columns
- Evidence in code:
  - [models.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/models.py)
  - `EmailDraftORM.draft_reasoning_artifact_ref`
- What is still open:
  - exact table shape for draft reasoning artifacts
  - whether the reference is a table row id, opaque artifact id, or another stable locator
  - artifact scope should stay limited to LLM-related reasoning paths, not general operational traces

### Decision 4: Final outbound email is a distinct `EmailMessage`
- Tickets: `HELM-48`, `HELM-52`
- Status: decided
- Decision:
  - final outbound email must be persisted as its own `EmailMessage`
  - it should be linked back to the originating draft through `source_draft_id`
  - `EmailDraft.final_sent_message_id` is the forward pointer
- Evidence in code:
  - [models.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/models.py)
  - [email_messages.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/repositories/email_messages.py)
- What is still open:
  - implementation of the send-attempt contract

### Decision 5: Metadata-first seed planning is thread-level and comes before deep processing
- Ticket: `HELM-51`
- Status: decided
- Decision:
  - seed routing starts with metadata-level thread planning
  - the buckets are `deep_seed`, `light_seed_only`, and `do_not_surface`
  - selection is evaluated at the thread level, not the raw-message level
- Evidence in code:
  - [seed.py](/Users/ankush/git/helm/packages/agents/src/email_agent/seed.py)
  - [email.py](/Users/ankush/git/helm/apps/api/src/helm_api/routers/email.py)
- What is still open:
  - persistence/queueing contract for turning seed decisions into queued deep-seed work

### Decision 6: Default follow-up timing is 3 business days, weekday-only, in the user-owned timezone
- Tickets: `HELM-49`, `HELM-58`
- Status: provisional
- Decision:
  - v1 baseline is weekday-only business-day math
  - no holiday calendar is assumed
  - timezone ownership should be the single user’s configured timezone, not sender-local timezone inference
  - default value remains `3`, stored in `EmailAgentConfig`
- Why this is a reasonable baseline:
  - it is conservative
  - it unblocks scheduling behavior without inventing enterprise calendar semantics
- What is still open:
  - where the timezone is surfaced/configured in the Email Agent boundary
  - whether future holiday support belongs in Email Agent or an external calendar service

### Decision 7: Send attempts are first-class Email Agent records
- Tickets: `HELM-52`, `HELM-58`
- Status: decided
- Decision:
  - send delivery attempts are stored as their own Email Agent object
  - send attempts are domain truth for delivery tries
  - `agent_runs` remains operational telemetry only
- Minimal v1 shape:
  - `draft_id`
  - `email_thread_id`
  - `attempt_number`
  - `status`
  - `failure_class`
  - `failure_message`
  - `provider_error_code`
  - `provider_message_id`
  - `started_at`
  - `completed_at`

### Decision 8: Send-attempt status is minimal and ambiguity is represented through failure class
- Tickets: `HELM-52`, `HELM-58`
- Status: decided
- Decision:
  - `EmailSendAttempt.status` values are:
    - `pending`
    - `failed`
    - `succeeded`
  - ambiguous provider-boundary outcomes are persisted as:
    - `status=failed`
    - `failure_class=unknown_delivery_state`
- Why:
  - product semantics remain simple
  - internal debugging still preserves uncertainty

### Decision 9: Automatic retries are allowed only for clearly retryable failures
- Tickets: `HELM-52`, `HELM-58`
- Status: decided
- Decision:
  - max automatic attempts in v1: `3` total
  - retryable failure classes:
    - `timeout`
    - `connection_error`
    - `rate_limited`
    - `provider_5xx`
  - non-retryable failure classes:
    - `invalid_recipient`
    - `invalid_payload`
    - `auth_error`
    - non-`429` `4xx`
    - `duplicate_send`
    - `unknown_delivery_state`
- Why:
  - transient transport failures should not create user friction
  - ambiguous or terminal failures should not auto-retry

### Decision 10: Retry authority stays simple after approval
- Tickets: `HELM-52`, `HELM-58`
- Status: decided
- Decision:
  - approval is attached to content, not transport
  - unchanged approved drafts can be manually retried without fresh approval
  - changed draft content requires fresh approval
  - every retry, automatic or manual, creates a new send-attempt row
- Why:
  - preserves low-friction retry behavior
  - keeps the audit trail complete

### Decision 11: Exhausted or ambiguous send outcomes surface for manual review
- Tickets: `HELM-52`, `HELM-58`
- Status: decided
- Decision:
  - after retry exhaustion:
    - `EmailDraft.approval_status` remains `approved`
    - `EmailDraft.status` becomes `send_failed`
  - `unknown_delivery_state` is manual-retry only
  - manual retry should warn about duplicate-send risk
  - final outbound `EmailMessage` is created only on provider-confirmed success
  - there may be many send attempts for one draft, but at most one successful send per draft

### Decision 12: Duplicate-send protection is local-only in v1
- Tickets: `HELM-52`, `HELM-58`
- Status: decided
- Decision:
  - dedupe is enforced by Email Agent local invariants
  - do not depend on provider idempotency support
- Core invariant:
  - at most one successful send per draft

## Decisions Still Open

These still need explicit resolution before the next implementation pass can safely continue.

### Open 1: Draft Reasoning Artifact Schema
- Tickets: `HELM-54`, `HELM-57`
- Needed decision:
  - dedicated table shape
  - linkage rules to `EmailDraft` and `ActionProposal`
  - whether multiple reasoning revisions are preserved per draft

### Open 2: Labeling Rubric Contract
- Ticket: `HELM-53`
- Status: mostly decided
- Locked decisions:
  - uncertain but potentially important email routes to `NeedsReview`
  - clearly low-signal email does not surface and gets no visible labels
  - `Urgent` only applies to surfaced threads
  - `NeedsReview` covers both classifier uncertainty and judgment-sensitive cases
  - `Action` is independent of draft existence
  - `NeedsReview` is exclusive with both `Action` and `Urgent`
  - surfaced + actionable + urgent yields `Action` + `Urgent`
  - confidence is a routing aid, not a downstream override system
  - low confidence routes to manual review
- Remaining work:
  - implement the authored rubric document in code

### Open 3: Drafting Rubric Contract
- Ticket: `HELM-54`
- Status: mostly decided
- Locked decisions:
  - generate a draft only when reply drafting is explicitly needed
  - v1 produces a single draft, not multiple candidates
  - one `EmailDraft` record is updated in place across refinements
  - every generation/refinement event creates its own reasoning artifact
  - approval is tied to exact content
  - material content change resets approval
  - `send_failed` drafts remain refinable
  - unchanged `send_failed` drafts can be retried under prior approval
- Remaining work:
  - implement the authored drafting rubric in code and prompt contracts

### Open 4: Policy Document Boundary
- Ticket: `HELM-55`
- Status: mostly decided
- Locked decisions:
  - policy defines high-level behavioral philosophy
  - rubric defines operational classification and drafting decisions
  - config defines tunable knobs
  - prefer surfacing over silent suppression under uncertainty
  - meaningful outbound action remains human-gated
  - drafting prioritizes usefulness and correctness over polish
  - the system must distinguish knowledge, inference, and uncertainty
  - do not invent unsupported context or commitments
  - insufficient drafting context routes to review
  - thread-local context outranks broader memory
  - memory may shape tone/style but not override explicit facts or user instructions
  - reduce cognitive load without hiding uncertainty or collapsing distinct states
  - stop, preserve state, and surface issues when safe continuation is not possible
- Remaining work:
  - use the policy document as the source for future implementation and prompt shaping

### Open 5: Deep-Seed Queue Contract
- Ticket: `HELM-51`
- Needed decision:
  - queue persistence object
  - worker ownership
  - replay/idempotency behavior for deep-seed work

## Recommended Next Iteration Order

1. Resolve `HELM-58`
- unblock send-path work without guessing

2. Resolve the remaining draft-artifact decision in `HELM-57`
- unlock draft reasoning persistence cleanly

3. Author `HELM-53`, `HELM-54`, and `HELM-55`
- convert classifier/drafting behavior from scaffolding into explicit architecture

4. Resume implementation in this order:
- `HELM-52` send scaffold
- next quality slices on classification and drafting
