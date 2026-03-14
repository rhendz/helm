# Project

## What This Is

Helm Orchestration Kernel is the durable workflow engine for Helm, a single-user internal AI system. It can run multi-step workflows with typed specialist dispatch, durable artifacts, approval-gated side effects, restart-safe resume, replay-aware recovery, and shared operator surfaces across API and Telegram. The representative weekly scheduling workflow proves the kernel end to end, including task and calendar specialists, approval checkpoints, outbound sync, and recovery/replay behavior.

## Core Value

Helm can execute multi-step, approval-gated workflows reliably enough that workflow state, artifacts, and side effects remain durable and inspectable across restarts and failures, with task/calendar sync protection as a core capability.

## Current State

- M001 (Helm Orchestration Kernel v1) is complete and validated the kernel across API, worker, Telegram, storage, and orchestration boundaries using a weekly scheduling workflow.
- Workflow persistence, specialist dispatch, approval checkpoints, outbound sync, replay, and operator surfaces are implemented and covered by tests.
- The repo also contains older agent-specific plans and integrations (email, LinkedIn, Night Runner), underdeveloped domain layers (for example `packages/domain`), and historical docs/specs/tests that no longer represent the current product but still exist in the tree.
- `.gsd/milestones/M001/M001-SUMMARY.md` captures what was shipped in the kernel milestone and is the primary reference for kernel behavior.

## Architecture / Key Patterns

- Python monorepo with `apps/` (API, worker, Telegram bot) and `packages/` (orchestration, storage, connectors, agents, observability, domain).
- DB-first design with Postgres as the source of truth for workflow state, artifacts, sync records, and events.
- Orchestration logic lives in `packages/orchestration/src/helm_orchestration/` and owns workflow semantics, specialist dispatch, approval, sync execution, replay, and status projection.
- Storage models and repositories live in `packages/storage/src/helm_storage/` and implement workflow_* tables and related persistence.
- Connectors (task/calendar) live in `packages/connectors/src/helm_connectors/` and are invoked via adapter contracts.
- Agents (including EmailAgent and StudyAgent) live in `packages/agents/src/helm_agents/`.
- Operator surfaces are provided by FastAPI in `apps/api` and Telegram commands in `apps/telegram-bot`, backed by shared status/replay services.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping across M001 and M002.

## Milestone Sequence

- [x] M001: Helm Orchestration Kernel v1 — Durable workflow kernel with a representative weekly scheduling workflow and shared operator surfaces.
- [ ] M002: Helm Truth-Set Cleanup — Strict workflow-engine truth set, aggressive removal of stale/aspirational artifacts, and verified task/calendar workflow protection after cleanup.
  - Working inventory for M002 cleanup: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`.
