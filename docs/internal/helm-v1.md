# Helm V1 — Current Architecture

**Last updated:** 2026-03-13 (M002 corrective pass)

This document describes what Helm is **right now**. For the authoritative definition of current truth, see `.gsd/milestones/M002/M002-TRUTH-NOTE.md`.

---

## What Helm Is

Helm is a personal AI workflow engine for a single user. It executes multi-step workflows with:

- **Durable state** — workflow runs, steps, artifacts, and events are persisted in Postgres
- **Typed specialist dispatch** — task and calendar adapters are embedded workflow capabilities
- **Approval-gated side effects** — humans approve before outbound writes (sync, scheduling)
- **Restart-safe resume** — workflows can pause/fail/recover without losing state
- **Replay-aware recovery** — failed sync operations can be retried/replayed with lineage preservation
- **Shared operator surfaces** — API and Telegram bot backed by a unified workflow status projection

The core truth set is the **workflow engine plus task/calendar sync protection**. This version does not define multi-agent systems or broad automation as truth; those layers remain present but non-truth-defining.

---

## Operator Surfaces

### API (`apps/api`)

FastAPI server providing:

- Workflow creation (`POST /workflows`)
- Workflow status projection (`GET /workflows/{id}`)
- Approval decision (`POST /workflows/{id}/approvals/{checkpoint_id}/decide`)
- Replay request (`POST /workflows/{id}/replay`)
- Artifact lineage inspection (`GET /workflows/{id}/artifacts`)

### Telegram Bot (`apps/telegram-bot`)

Telegram commands for:

- `/workflows_create` — create a new workflow
- `/workflows_status` — view workflow status and completion summary
- `/workflows_approve` — issue an approval decision
- `/workflows_replay` — request replay of a failed sync

### Worker (`apps/worker`)

Persistent background process executing:

- `workflow_runs` job — orchestrates workflow steps, advance state machine, handle approvals
- `workflow_sync_records` job — executes approved sync operations, records outcomes, manages recovery
- Other agent-specific jobs (email, study) — non-truth but present for this version

---

## Core Capabilities

### Workflow Persistence

- `workflow_runs` — workflow execution instances with status (created/running/blocked/completed/failed)
- `workflow_steps` — individual steps within a run (dispatch, approval, sync, completion)
- `workflow_artifacts` — durable payloads (proposals, decisions, sync records, summaries)
- `workflow_events` — full lineage of state transitions and decisions

All stored in `packages/storage` with typed SQLAlchemy models and repositories.

### Specialist Dispatch

Task and calendar specialists are workflow adapters, not standalone agents:

- **Task adapter** (`packages/connectors/task_system.py`) — normalizes tasks, upserts into task system
- **Calendar adapter** (`packages/connectors/calendar_system.py`) — creates/updates calendar blocks
- Invocations are registered with the orchestration kernel and tracked in `workflow_specialist_invocations` table
- Specialist behavior is exercised end-to-end by the representative weekly scheduling workflow

### Approval Checkpoints

- Workflows can pause at explicit approval steps (`await_schedule_approval`)
- Approval payloads contain proposal artifacts, target system, and proposed changes
- Operators approve/reject/request_revision via API or Telegram
- Revision requests create new proposal versions; approved decisions trigger sync execution
- All stored in `workflow_approval_checkpoints` table with artifact linkage

### Adapter-Gated Sync and Recovery

- Sync records are deterministic: (proposal_id, version, target_system, sync_kind, item_key) uniquely identify a write operation
- Adapters return normalized request/outcome/reconciliation envelopes
- Failed writes are classified as retryable or non-recoverable
- Replay creates new sync record lineage for the same item without rewriting prior history
- Recovery classification lives on durable rows, not inferred from error text

### Replay and Recovery

- Explicit replay requests are validated against `safe_next_actions` from the workflow status projection
- Replay jobs create new sync-record generation for the same planned items
- Prior execution history remains queryable via `workflow_sync_records` lineage
- Partial sync termination records partial counts instead of rewriting succeeded rows

### Representative Workflow

The **weekly scheduling workflow** is the single workflow that defines end-to-end behavior:

1. **Create** — user provides a free-form request via API or Telegram
2. **Normalize** — task agent normalizes the request into internal task representations
3. **Propose** — calendar agent creates a schedule proposal with constraints and rationale
4. **Approve** — workflow pauses at approval checkpoint; operator reviews and decides
5. **Sync** — approved schedule is executed against task and calendar adapters
6. **Complete** — workflow persists a final summary artifact with approval decision and sync outcomes
7. **Recover** — if sync fails, operator can retry or replay from a known safe point

This workflow exercises all kernel capabilities: persistence, dispatch, approval, sync, recovery, and operator surfaces.

---

## Present But Non-Truth

The following exist in the repo but do not define current truth:

### Agents

- **EmailAgent** — code and runtime remain in place; email ingest jobs and reconciliation sweeps are functional but non-truth
- **StudyAgent** — frozen for this version; no new kernel decisions depend on it

Helm-level email planning and study workflow artifacts are non-canonical and may be removed or quarantined in future iterations without affecting the kernel.

### Historical Integrations

- **LinkedIn** — no concrete connector exists; planned but not implemented
- **Night Runner** — experimental cron-like tooling; removed during M002 cleanup

### Underdeveloped Layers

- **packages/domain** — aspirational design reference; removed during M002 cleanup with zero imports
- Historical product specs and planning docs predate the kernel and should not steer future architecture

---

## Diagnostic Entry Points

When verifying Helm behavior:

- **Workflow health:** `uv run --frozen --extra dev pytest -q tests/unit tests/integration` (14 tests covering kernel, task/calendar, approval checkpoints, sync integrity)
- **Truth definition:** `.gsd/milestones/M002/M002-TRUTH-NOTE.md`
- **Classification inventory:** `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` (what is keep/freeze/deprecate/remove)
- **UAT script:** `.gsd/milestones/M002/slices/S03/uat.md` (operator-driven end-to-end workflow verification)

---

## Future Direction

This version is workflow-engine-centric. Future milestones can extend Helm by:

1. Adding new workflow types that reuse the same kernel contracts (runs, steps, artifacts, approvals, sync, replay)
2. Introducing additional agents only after grounding their truth status back into the kernel contracts
3. Expanding operator surfaces (dashboards, new integrations) while keeping them backed by the shared status projection

No new architectural decisions should be made based on email, study, LinkedIn, or Night Runner unless those paths are explicitly reclassified and grounded in the kernel.
