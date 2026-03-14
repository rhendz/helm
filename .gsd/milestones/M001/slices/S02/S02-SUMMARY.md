# S02: Specialist Dispatch And Approval Semantics

**Implemented kernel-owned specialist dispatch for TaskAgent and CalendarAgent, durable invocation records, approval checkpoints, and revision-driven proposal versioning.**

## What Happened

S02 turned S01's workflow state machine into a typed specialist execution kernel with approval gating. T01 added a dedicated `workflow_specialist_invocations` table and typed TaskAgent/CalendarAgent payload schemas with semantic step registration and worker wiring. T02 added a `workflow_approval_checkpoints` table, checkpoint creation from schedule proposals, and kernel-owned approve/reject/revision decision handling with automatic resume semantics. T03 completed the approval story with revision-linked proposal versioning, supersession lineage via `lineage_parent_id` and `supersedes_artifact_id`, version-targeted operator decisions, and latest-first status projections across API and Telegram.

## Key Outcomes

- Durable specialist invocation records with input/output artifact linkage.
- Typed TaskAgent and CalendarAgent dispatch keyed by `(workflow_type, step_name)`.
- Approval checkpoints with allowed actions and decision metadata.
- Revision feedback creates new proposal versions while preserving supersession history.
- Version-targeted approval, rejection, and revision actions in both API and Telegram.
- Shared checkpoint-aware workflow status projection.

## Verification

- `test_workflow_repositories.py`: schedule proposal lineage, specialist invocation persistence.
- `test_workflow_orchestration_service.py`: specialist execution, approval pause, approve-to-resume, reject-to-close, revision-to-regenerate, multi-revision correctness.
- `test_workflow_status_service.py`: version-aware status projection and decision lineage.
- `test_workflow_status_routes.py`: version-aware API routes and version-targeted approvals.
- `test_telegram_commands.py`: concrete-target approval and version inspection flows.

## Tasks

- T01 (6 min): Specialist invocation persistence, typed dispatch contracts, worker wiring.
- T02 (9 min): Approval checkpoint storage, decision handling, shared API/Telegram surfaces.
- T03 (15 min): Revision-linked proposal versioning and version-targeted operator actions.
