# 01 — Helm v1 PRD

## Overview

Helm is a personal operations assistant that helps a user capture items, clarify them when needed, and turn them into well-scheduled actions.

Helm v1 is a **web-first personal operations console**. Its job is not to autonomously complete everything a user asks. Its job is to interpret incoming items, ask only for missing scheduling-relevant information, and propose the best supported next action based on its current capabilities.

In v1, the primary supported action is **scheduling time on the user’s calendar**.

## Core promise

Tell Helm what you need handled. Helm will:

* capture the item durably
* interpret what it means
* ask only for missing time, sizing, or preference/context needed to schedule well
* propose a schedule block for approval
* keep unsupported items visible instead of losing them

## Audience

### Primary

* the founder/operator

### Early cohort

* a small trusted invite-only set of friends/colleagues

### Longer-term target

* high-agency professionals with recurring coordination overhead, fragmented obligations, and calendar pressure

## v1 wedge

### Real differentiator

Better intake, clarification, and personal context than generic schedulers.

### Visible payoff

Well-scheduled actions appearing on the calendar.

## Non-goals for v1

Helm v1 is not:

* a full autonomous agent executor
* a full task manager with completion tracking, rollover, and follow-through
* a recurrence/habit system
* a multi-source intake platform
* an email-first product
* a no-approval automation system
* a system that splits one task into multiple schedule blocks

## Product principles

* Helm should choose the best supported outcome from its actual enabled capabilities.
* Helm should not ask the user to choose among actions Helm already knows it can or cannot perform.
* Helm should ask only for information required to schedule well.
* Helm should store items durably even when it cannot act on them yet.
* Helm should remain honest about unsupported actions.
* Helm should be console-first in v1, with a path toward a more secretary-like experience later.

## Input model

### Supported intake in v1

* manual text input in the web app

### Transitional intake/notification surface

* Telegram may remain enabled as a secondary intake and notification channel during transition

### Example inputs

* “book dentist appointment this week”
* “study system design for 2 hours this week”
* “buy groceries tomorrow evening”
* “follow up with John on Friday”
* “handle tax thing”

## Supported outcomes in v1

Each task has exactly one primary outcome in v1.

### Primary supported outcome

* **schedule**: propose a concrete calendar time block for approval

### Additional system behaviors

* **clarify**: ask for missing scheduling-relevant information
* **capture unsupported**: keep the item visible if Helm cannot act yet

## Clarification policy

Helm may ask clarification questions only when required to schedule well.

Allowed clarification categories:

* missing temporal information
* missing sizing/duration information
* missing user preference/context needed for scheduling

Helm should not ask questions about unsupported execution paths in v1.

### Clarification UX

* bounded missing information → structured form
* broader ambiguity → one question at a time

## Approval model

All scheduling actions require approval in v1.

Auto-approval may be introduced later, but it is not part of the default v1 behavior.

## Scheduling policy

### Hard boundaries

Temporal expressions like “this week” should be treated as hard boundaries in v1.

### One block per task

In v1, one task maps to at most one schedule block.

### Determinism

The LLM should not directly decide final schedule dates. The target v1.1 behavior is:

* LLM extracts structured temporal intent
* deterministic resolver maps intent to a concrete window/date
* slot finder places the block on calendar
* user approves
* sync occurs

## Unsupported items

If Helm cannot act on an item, it should:

* capture it durably
* mark it unsupported
* keep it visible in the inbox

Unsupported items should not disappear silently.

## Onboarding

v1 onboarding captures:

* timezone
* working hours
* calendars to consider
* preferred focus block length
* preferred meeting hours
* preferred days/times for deep work

Helm may learn refinements later from behavior, but the v1 system starts with explicit user input.

## Success criteria

A successful v1 experience looks like:

* user enters an item
* Helm captures it immediately
* Helm either asks a bounded clarification question or proposes a schedule block
* the user approves
* the calendar block syncs reliably
* the item remains visible with an accurate state

## v1 scope summary

Helm v1 is a web-first inbox and scheduling console for manually entered items. It focuses on interpretation, clarification, and approval-gated scheduling. It does not yet own long-term follow-through, completion tracking, or broad autonomous execution.

---

# 02 — Helm v1 Domain Model and State PRD

## Overview

Helm needs a first-class domain model separate from workflow execution.

The existing system conflates:

* the user’s requested work item
* the system’s execution record
* the calendar synchronization result

That must be split.

## Core entities

### Task

A Task is the first-class domain object representing an item the user wants Helm to help handle.

A task may:

* be newly captured
* need clarification
* be ready to schedule
* be scheduled
* be unsupported
* later be resolved or canceled

A task may exist even if no schedule block has been proposed yet.

#### Suggested fields

* `id`
* `user_id`
* `source_type`
* `source_ref`
* `raw_text`
* `title`
* `description`
* `status`
* `priority`
* `estimated_minutes`
* `temporal_intent_json`
* `clarification_needed_json`
* `supported_outcome`
* `created_at`
* `updated_at`

### ScheduleBlock

A ScheduleBlock is the concrete proposed or synced chunk of calendar time associated with a task.

Example:

* Task: “Study system design this week”
* ScheduleBlock: Thursday 7:00pm–8:00pm

In v1, a task may have at most one schedule block.

A schedule block may exist before approval as a proposed block.

#### Suggested fields

* `id`
* `task_id`
* `calendar_id`
* `start_at`
* `end_at`
* `status`
* `proposal_version_number`
* `external_event_id`
* `created_at`
* `updated_at`

### WorkflowRun

A WorkflowRun is an execution record for system processing.

It is not the domain identity of the task.

A workflow run may:

* parse an item
* request clarification
* create a proposal
* wait for approval
* resume and sync

`workflow_runs` should gain a `task_id` foreign key so runs can attach to domain objects.

### Proposal

A Proposal is a versioned artifact representing Helm’s proposed next action, usually a scheduling proposal in v1.

The current artifact/checkpoint system can continue to represent proposals.

### UserSchedulingProfile

A UserSchedulingProfile stores onboarding and scheduling-preference data.

#### Suggested fields

* `user_id`
* `timezone`
* `working_hours_json`
* `calendar_ids_json`
* `preferred_focus_block_minutes`
* `preferred_meeting_hours_json`
* `preferred_deep_work_windows_json`
* `created_at`
* `updated_at`

## State model

### Task.status

The v1 task states are:

* `captured`
* `needs_clarification`
* `ready_to_schedule`
* `scheduled`
* `unsupported`
* `resolved`
* `canceled`

#### Meaning

* `captured`: item was received and stored
* `needs_clarification`: Helm cannot schedule well without more info
* `ready_to_schedule`: Helm has enough information to prepare/propose a block
* `scheduled`: approved and synced to calendar
* `unsupported`: captured but Helm cannot act on it yet
* `resolved`: completed/closed manually or by future capability
* `canceled`: intentionally dismissed

### ScheduleBlock.status

The v1 schedule block states are:

* `proposed`
* `approved`
* `synced`
* `failed`
* `canceled`

#### Meaning

* `proposed`: Helm generated a candidate block
* `approved`: user approved the proposal
* `synced`: block successfully created/updated in calendar
* `failed`: sync failed
* `canceled`: proposal withdrawn or canceled

### WorkflowRun.status

Workflow state remains execution-focused, for example:

* `pending`
* `running`
* `blocked`
* `resumable`
* `completed`
* `failed`

## Why these state layers must remain separate

### Task state

Answers:

* what is happening with the user’s item?

### ScheduleBlock state

Answers:

* what is happening with the proposed/synced time reservation?

### WorkflowRun state

Answers:

* what is the system doing internally right now?

Without this separation, the system incorrectly treats “calendar sync completed” as “user work completed.”

## Example lifecycle

Input:
“Study system design for 2 hours this week”

Possible flow:

1. Task created with `captured`
2. Helm infers enough info → Task becomes `ready_to_schedule`
3. ScheduleBlock created with `proposed`
4. WorkflowRun enters approval wait state
5. User approves
6. ScheduleBlock becomes `approved`
7. Calendar sync succeeds → ScheduleBlock becomes `synced`
8. Task becomes `scheduled`
9. WorkflowRun becomes `completed`

## Clarification model

A task enters `needs_clarification` when Helm lacks enough information for quality scheduling.

The missing information should be stored explicitly in structured form, not hidden in logs or dropped entirely.

Suggested storage:

* `clarification_needed_json`
* fields missing
* prompt/form metadata
* clarification history later if needed

## Temporal intent model

The current system directly uses an LLM-generated date string.

That should evolve toward structured temporal intent, stored on the task.

Example shape:

* anchor: `this_week`
* constraint_type: `within_range`
* day_preference: `weekday`
* time_preference: `morning`

This allows deterministic resolution and better testing.

## V1 domain constraints

* one task may have zero or one schedule block
* one workflow run may reference one task
* a task may exist without a schedule block
* a schedule block may exist before approval
* unsupported tasks remain first-class visible objects

---

# 03 — Helm v1 Architecture and Surfaces PRD

## Overview

Helm should remain in the current repo and evolve through a new product surface rather than a full rewrite.

The repo already contains meaningful reusable infrastructure:

* storage
* provider integrations
* orchestration kernel
* observability
* API surface
* worker execution shell

The right move is a product-layer reset, not a platform reset.

## Architectural direction

### Keep

* existing repo
* FastAPI backend
* Postgres as source of truth
* current workflow engine for the next milestone
* provider abstractions
* LLM client wrapper
* observability stack

### Add

* first-class `tasks` table
* first-class `schedule_blocks` table
* `task_id` foreign key on `workflow_runs`
* new web app surface
* internal admin/debug panel

### Refactor

* `/task` product flow
* scheduling-specific orchestration handlers
* approval execution path
* task identity away from `run_id` as user-facing anchor

## Surface architecture

### Frontend

* **Next.js**
* web-first user-facing product
* inbox-first experience
* task detail and approval UI
* onboarding flow
* clarification forms

### Backend

* **FastAPI**
* existing API remains backend foundation
* add task-centric endpoints and projections
* keep workflow/replay/approval infrastructure where useful

### Internal admin/debug

* **SQLAdmin**
* mounted against existing SQLAlchemy models
* used to inspect and repair state, inspect tasks/runs/sync records, and support early cohort operations

### Transitional channels

* Telegram remains available as:

  * intake surface
  * notification surface

Telegram is no longer the primary product surface.

## UI surfaces

### Inbox

The inbox is the default home view.

It should show tasks across statuses, with filtering focused on:

* needs attention
* needs clarification
* ready to schedule
* scheduled
* unsupported

### Task detail

Task detail should show:

* original input
* parsed interpretation
* missing information if any
* proposed schedule block
* approval actions
* relevant workflow/debug context for internal users

### Clarification UI

Clarification should be:

* structured when missing information is obvious and bounded
* conversational only when ambiguity is broader

### Onboarding

The onboarding flow collects:

* timezone
* working hours
* calendars to consider
* preferred focus block length
* preferred meeting hours
* preferred days/times for deep work

## Execution architecture

### Current engine

The current workflow engine already provides meaningful reusable primitives:

* step execution
* approval checkpoints
* sync records
* replay/recovery
* generic workflow state handling

It should remain in place for the next milestone.

### Approval path

The approve path should move fully back to the worker.

The frontend or Telegram approval action should:

* mark approval
* return immediately

The worker should:

* resume execution
* perform sync
* handle retries/idempotency
* emit completion/failure notifications

This removes fragile synchronous execution from the user-facing surface.

### Scheduling architecture

The current date-selection logic is too LLM-driven.

Target architecture:

1. user input captured
2. LLM extracts structured semantics, including temporal intent
3. deterministic resolver converts temporal intent into a concrete date/window
4. slot finder locates actual free time on the calendar
5. schedule proposal artifact is created
6. user approves
7. worker syncs to calendar

### Reliability priorities

Immediate priorities:

* worker-owned approve path
* deterministic temporal resolution
* task as first-class domain object
* visible task states in web UI

### Why not Temporal yet

Temporal remains a plausible future evolution, but not a current prerequisite.

Reason:

* the current workflow kernel is more reusable than expected
* the main missing pieces are domain model and product semantics
* changing workflow runtime now would add churn before the product model stabilizes

The architecture should remain open to a future Temporal migration, but should not require it for v1.1.

## Repo strategy

### Same repo

Use the current monorepo.

### New surface

Add a new web/product surface rather than replacing everything in place immediately.

### Reuse boundaries

Preserve:

* `packages/storage`
* orchestration kernel
* providers
* llm wrapper
* observability
* worker shell
* much of `apps/api`

Refactor or replace:

* scheduling-specific orchestration code
* task execution path
* Telegram-first UX assumptions
* user-facing run-centric identity

## Recommended implementation sequence

1. add `tasks` table
2. add `schedule_blocks` table
3. add `task_id` to `workflow_runs`
4. move approve execution fully to worker
5. introduce structured temporal intent + deterministic resolver
6. add task-centric API projections
7. build Next.js inbox/detail/onboarding surfaces
8. add SQLAdmin for internal operations/debugging
9. retain Telegram as secondary intake/notification surface during transition

## Success criteria for the architecture

The next version of Helm should allow:

* a user to capture an item in the web app
* the system to persist a first-class task immediately
* Helm to clarify missing information when needed
* Helm to propose a schedule block for approval
* the worker to sync that block reliably after approval
* the inbox to reflect accurate item state throughout