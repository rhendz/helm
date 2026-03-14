# M002 Workflow-Engine Truth Note

## Purpose

This note defines the **current-version Helm truth set** for M002, centered on the workflow engine and the representative weekly scheduling workflow. It is the source of truth for what "Helm is" for planning, cleanup, and future work.

Anything outside this truth set may still exist in the repo, but it is not allowed to silently redefine product or architecture decisions.

## Truth-Defining Kernel

The workflow-engine truth set is defined by the following kernel capabilities and artifacts from M001:

- **Durable workflow kernel**
  - workflow_runs, workflow_steps, workflow_artifacts, workflow_events tables
  - Typed SQLAlchemy models and repositories in `packages/storage`
  - Orchestration state machine in `packages/orchestration` owning validation, step advancement, failure persistence, and restart-safe resume
- **Typed specialist dispatch**
  - TaskAgent and CalendarAgent contracts and invocation records
  - Specialist registration keyed by (workflow_type, step_name)
- **Approval checkpoints and revision semantics**
  - workflow_approval_checkpoints table
  - Proposal/version linkage and revision-oriented decisions
- **Adapter-gated sync and recovery**
  - workflow_sync_records table with deterministic identity and lineage
  - Adapter protocols with normalized request/outcome/reconciliation envelopes
  - Recovery classification and replay vs retry semantics on durable rows
- **Shared operator surfaces**
  - API workflow routes and Telegram commands backed by a shared status projection
  - Replay and recovery entry points via API, worker, and Telegram

These behaviors and contracts are authoritative for Helm's current workflow engine. M001-SUMMARY and the code paths it references are the canonical behavioral reference.

## Representative Workflow Truth

The **representative weekly scheduling workflow** is the single workflow that defines end-to-end behavior for this version:

- Shared request contract for weekly scheduling
- Deterministic normalization into internal task representations
- Schedule proposal artifacts with constraints and carry-forward rationale
- Explicit approval checkpoint with revision cycles
- Adapter-gated sync execution for task and calendar systems
- Final summary and completion projection derived from durable artifacts and sync records

For M002, **any new workflow type is non-truth** unless it:

1. Reuses the same kernel contracts (runs, steps, artifacts, approvals, sync, replay), and
2. Is verified at a similar depth to the weekly scheduling workflow (tests + runbook coverage).

## Operator Surfaces In Scope

The following operator surfaces are part of the workflow-engine truth set:

- **FastAPI API** workflows and replay routes in `apps/api`
- **Telegram bot** workflow and approval commands in `apps/telegram-bot`
- Shared workflow status and replay services that back both surfaces

Operator behavior must be consistent with the shared status projection and replay service established in M001. Any additional surfaces (dashboards, experimental UIs) are non-truth for this milestone.

## Shared Workflow Capabilities

For M002, **task/calendar sync protection is a protected shared workflow capability**, not an agent-centric architecture.

- **Protected capabilities (truth-defining)**
  - Task and calendar adapters embedded in the workflow engine (`packages/connectors`)
  - Task and calendar specialist invocation contracts registered with the orchestration kernel
  - Outbound sync semantics (adapter protocols, recovery classification, replay behavior)
  - These are *workflow primitives*, not standalone agent products

- **Additional agents (present but non-truth)**
  - EmailAgent: code and storage contracts remain in place; Helm-level email planning artifacts are non-canonical
  - StudyAgent: frozen for this version; no new kernel or architecture decisions may depend on StudyAgent behavior

Agent behavior (email, study) may be useful or partially working, but:

- Their specs, prompts, and planning documents **do not define Helm's current truth set**.
- The workflow engine and task/calendar sync protection are the only architectural decisions that are truth-defining.
- Future milestones can reintroduce agent-specific truth, but only by grounding it back into the established kernel contracts.

The core truth is the **workflow-engine-centric design**, not a multi-agent system.

## Truth-Set Boundaries

The following categories explicitly **do not define** the current truth set, even when they share code paths or tables:

- Legacy or aspirational email flows (including email replay workers)
- LinkedIn integrations
- Night Runner or other experimental/cron-like flows
- Underdeveloped domain layers such as `packages/domain`
- Historical specs, docs, and tests that predate M001 or assume multi-agent products beyond the current kernel

These artifacts may be:

- Removed,
- Deprecated/archived,
- Or quarantined for reference,

in later slices under R002/R005. Their existence must not override or dilute the kernel-oriented truth defined here.

## How This Note Is Used

This truth note is the **anchor** for:

- M002/S01 classification rules (keep/freeze/deprecate/remove/quarantine)
- M002/S02 cleanup decisions and working-set reduction
- M002/S03 verification that task/calendar workflows remain intact
- Requirements R001 and R004 in `.gsd/REQUIREMENTS.md`, which reference this note as their proof surface

When in doubt:

- Prefer kernel artifacts and the weekly scheduling workflow described in `.gsd/milestones/M001/M001-SUMMARY.md`.
- Treat non-core agents and historical integrations as non-truth unless explicitly reclassified in M002.
