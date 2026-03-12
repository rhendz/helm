# Helm Orchestration Kernel v1

## What This Is

Helm Orchestration Kernel v1 is the durable workflow engine for Helm, a personal internal AI system. It is responsible for running multi-step workflows reliably, dispatching specialist agents such as `TaskAgent` and `CalendarAgent`, pausing for human approval before meaningful side effects, persisting structured artifacts, surviving restarts, and resuming safely after failures.

This work is not about expanding Helm's end-user domain coverage yet. It is about establishing the core kernel that future Helm workflows can reuse through clean orchestration, storage, and adapter boundaries.

## Core Value

Helm can execute multi-step, approval-gated workflows reliably enough that workflow state, artifacts, and side effects remain durable and inspectable across restarts and failures.

## Requirements

### Validated

- ✓ Telegram is the primary control surface for V1 approval and status interactions — existing
- ✓ Postgres-backed durable artifacts and workflow-related state already exist as the system of record — existing
- ✓ Worker-driven background execution already exists for scheduled and replayable jobs — existing
- ✓ Human-supervised outbound actions are already an established V1 behavior — existing
- ✓ External integrations already flow through connector and adapter-style boundaries in parts of the codebase — existing

### Active

- [ ] Helm can create a durable workflow run from a user request and track current status, step, and lineage.
- [ ] Helm can dispatch specialist agents such as `TaskAgent` and `CalendarAgent` as typed workflow steps with persisted invocation records.
- [ ] Helm can persist structured workflow artifacts after each major step, including raw input, normalized tasks, schedule proposals, approvals, and final summaries.
- [ ] Helm can validate intermediate outputs and persist warnings or ambiguity flags before downstream execution continues.
- [ ] Helm can pause at approval checkpoints before meaningful external writes and resume safely after approve, reject, or revision decisions.
- [ ] Helm can survive worker or process restarts and resume in-flight workflows from durable state without losing lineage.
- [ ] Helm can record downstream adapter writes, external object IDs, and execution outcomes for task-system and calendar side effects.
- [ ] Helm can recover cleanly from failures with explicit run state, persisted errors, and replayable/resumable execution paths.
- [ ] Helm includes one representative end-to-end kernel demo: converting a weekly scheduling request into structured tasks, a proposed schedule, an approval checkpoint, and approved downstream writes.

### Out of Scope

- Email-specific workflow expansion — the current focus is the reusable kernel, not inbox/domain feature growth.
- Study-specific workflow expansion — kernel infrastructure comes first so later study flows inherit durable orchestration.
- Broad new product workflows beyond one representative scheduling demo — avoid scope creep while the kernel contract is still being established.
- New primary interfaces or dashboards — Telegram-first remains the V1 interaction model.
- Unsupervised outbound side effects — meaningful writes must remain behind explicit approval.
- Multi-tenant or public-product abstractions — V1 remains a single-user internal system.

## Context

Helm already exists as a brownfield Python monorepo with three runtime entry points: API, worker, and Telegram bot. The repo's product contract in `docs/internal/helm-v1.md` is personal-first, artifact-driven, DB-first, modular, and human-supervised for important actions.

The current codebase already demonstrates durable artifact persistence and background execution, especially in the email workflow. Postgres is the system of record, SQLAlchemy repositories already own most durable state, and run-tracking plus replay/control surfaces already exist. These are the foundations the orchestration kernel should build on rather than replace.

The main architectural gap is that workflow orchestration is not yet a clear reusable kernel. LangGraph usage and workflow-specific runtime behavior are still concentrated inside domain agent code, especially the email path, while `packages/orchestration` remains mostly a placeholder. This project establishes that missing kernel layer so specialist agents can plug into a consistent workflow contract.

The representative v1 kernel scenario is a weekly scheduling workflow. A user asks Helm to fit a set of tasks into the week. Helm creates a workflow run, invokes `TaskAgent` to normalize the work, validates and persists the result, invokes `CalendarAgent` to produce a schedule proposal, pauses for approval, and only after approval writes through task-system and calendar adapters. Every major step produces durable artifacts and lineage.

The immediate priority is reliability, not feature breadth. The point of this project is to ensure workflows survive restarts, recover from failure, and make all major decisions and side effects inspectable.

## Constraints

- **Product Scope**: Single-user internal system only — the repo spec explicitly rejects multi-tenant and public-product abstractions for V1.
- **Primary UX**: Telegram-first interaction model — approvals, status, and lightweight workflow interaction should continue to fit the existing V1 UI contract.
- **Persistence**: Postgres is the source of truth — workflow state and artifacts must live in durable storage, not prompt memory.
- **Safety**: Human approval is required before meaningful outbound actions — adapter writes to external systems cannot bypass approval gates.
- **Architecture**: Preserve explicit package boundaries — app layers orchestrate while reusable kernel logic belongs in package boundaries, especially `packages/orchestration`, `packages/storage`, and adapter-facing packages.
- **Execution Style**: Build on existing worker/replay patterns where possible — the kernel should align with current background execution and run-tracking primitives instead of introducing unnecessary new infrastructure.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Focus V1 on the orchestration kernel rather than expanding email or study flows | Reliability and reusable workflow infrastructure are the immediate bottlenecks | — Pending |
| Use one representative scheduling workflow to exercise the kernel end to end | A concrete workflow is needed to validate dispatch, persistence, approval, resume, and side effects | — Pending |
| Keep approval gates before any meaningful external writes | The repo's V1 contract is human-supervised outbound behavior | — Pending |
| Treat `TaskAgent` and `CalendarAgent` as plug-in specialists invoked by the kernel | Specialist behavior should be reusable through a common orchestration contract | — Pending |
| Preserve DB-first artifacts and workflow lineage across every major step | Durable artifacts are a core product philosophy and are required for restart recovery and debugging | — Pending |
| Keep Telegram as the primary operator surface for V1 | This matches the existing product spec and avoids UI scope expansion during kernel work | — Pending |

---
*Last updated: 2026-03-11 after initialization*
