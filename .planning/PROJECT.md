# Helm Orchestration Kernel

## What This Is

Helm Orchestration Kernel is the durable workflow engine for Helm, a personal internal AI system. It now ships a reusable kernel that can run multi-step workflows with typed specialist dispatch, durable artifacts, approval-gated side effects, restart-safe resume, replay-aware recovery, and shared operator surfaces across API and Telegram.

The shipped `v1.0` proof point is the weekly scheduling workflow, which carries a request from raw intake through normalized tasks, schedule proposal, approval checkpoint, approved downstream writes, and replay-aware final lineage.

## Core Value

Helm can execute multi-step, approval-gated workflows reliably enough that workflow state, artifacts, and side effects remain durable and inspectable across restarts and failures.

## Current State

- **Shipped milestone:** `v1.0` on `2026-03-14`
- **Milestone archive:** [v1.0-ROADMAP.md](/Users/ankush/git/helm/.planning/milestones/v1.0-ROADMAP.md)
- **Requirements archive:** [v1.0-REQUIREMENTS.md](/Users/ankush/git/helm/.planning/milestones/v1.0-REQUIREMENTS.md)
- **Audit status:** passed at [v1.0-v1.0-MILESTONE-AUDIT.md](/Users/ankush/git/helm/.planning/v1.0-v1.0-MILESTONE-AUDIT.md)

## Requirements

### Validated

- ✓ Durable workflow runs, steps, artifacts, and lineage are persisted and inspectable — `v1.0`
- ✓ Typed `TaskAgent` and `CalendarAgent` dispatch with durable invocation records — `v1.0`
- ✓ Approval checkpoints, revision-driven proposal versioning, and kernel-owned resume semantics — `v1.0`
- ✓ Adapter-gated sync execution with idempotency, retry, replay, and recovery classification — `v1.0`
- ✓ Representative weekly scheduling workflow from request through approved writes and replay-aware final lineage — `v1.0`
- ✓ Telegram and API operator tooling for workflow status, approval, replay, and lineage inspection — `v1.0`

### Active

- [ ] Compare proposal revisions before approving a later attempt.
- [ ] Register and invoke additional specialist agents through the same typed kernel contract.
- [ ] Run additional domain workflows, such as email or study flows, on the same kernel contract.
- [ ] Coordinate multiple workflow templates with shared artifact and adapter infrastructure.

### Out of Scope

- New primary dashboard or web UI while Telegram remains the primary operator surface.
- Unsupervised outbound writes that bypass explicit approval.
- Multi-tenant or public-product abstractions.
- Broad workflow expansion before the next milestone explicitly defines scope.

## Next Milestone Goals

- Decide the first post-kernel workflow expansion to run on the shipped orchestration core.
- Add richer operator tooling where it materially improves approval and replay workflows.
- Preserve the DB-first, shared-surface, approval-gated kernel architecture while broadening workflow breadth.

## Context

The repo now contains a working orchestration kernel across API, worker, Telegram, orchestration, and storage boundaries. `v1.0` established the reusable kernel contract rather than expanding end-user product breadth. The next milestone should build on that proven base instead of reopening the kernel foundations.

## Constraints

- **Product Scope:** Single-user internal system only.
- **Primary UX:** Telegram-first interaction model.
- **Persistence:** Postgres remains the source of truth for workflow state and artifacts.
- **Safety:** Meaningful external writes require explicit approval.
- **Architecture:** App layers orchestrate while reusable behavior stays in package boundaries.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Focus V1 on the orchestration kernel rather than expanding email or study flows | Reliability and reusable workflow infrastructure were the immediate bottlenecks | ✓ Shipped in v1.0 |
| Use one representative scheduling workflow to exercise the kernel end to end | A concrete workflow was needed to validate dispatch, persistence, approval, resume, and side effects | ✓ Shipped in v1.0 |
| Keep approval gates before any meaningful external writes | The repo's V1 contract is human-supervised outbound behavior | ✓ Shipped in v1.0 |
| Treat `TaskAgent` and `CalendarAgent` as plug-in specialists invoked by the kernel | Specialist behavior should be reusable through a common orchestration contract | ✓ Shipped in v1.0 |
| Preserve DB-first artifacts and workflow lineage across every major step | Durable artifacts are required for restart recovery, replay, and debugging | ✓ Shipped in v1.0 |
| Keep Telegram as the primary operator surface for V1 | This matched the product spec and avoided UI scope expansion during kernel work | ✓ Shipped in v1.0 |

---
*Last updated: 2026-03-14 after v1.0 milestone*
