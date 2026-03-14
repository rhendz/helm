# Project

## What This Is

Helm Orchestration Kernel is the durable workflow engine for Helm, a single-user internal AI system. It can run multi-step workflows with typed specialist dispatch, durable artifacts, approval-gated side effects, restart-safe resume, replay-aware recovery, and shared operator surfaces across API and Telegram. The representative weekly scheduling workflow proves the kernel end to end, including task and calendar specialists, approval checkpoints, outbound sync, and recovery/replay behavior.

## Core Value

Helm can execute multi-step, approval-gated workflows reliably enough that workflow state, artifacts, and side effects remain durable and inspectable across restarts and failures, with task/calendar sync protection as a core capability.

## Current State

- M001 (Helm Orchestration Kernel v1) is complete and validated the kernel across API, worker, Telegram, storage, and orchestration boundaries using a weekly scheduling workflow.
- Workflow persistence, specialist dispatch, approval checkpoints, outbound sync, replay, and operator surfaces are implemented and covered by tests.
- M002/S01 defined a small, explicit workflow-engine truth set and classification rules, anchored on task/calendar workflows and operator surfaces, with EmailAgent deprecated and StudyAgent frozen.
- M002/S02 applied that truth set to the repo tree:
  - Deprecated and aspirational surfaces (Night Runner, packages/domain, LinkedIn, Email/Study docs/tests) are classified as keep/freeze/deprecate/quarantine in `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`.
  - `packages/domain` has been quarantined under `docs/archive/packages-domain/` and removed from all runtime PYTHONPATH helpers.
  - Night Runner exists only as deprecated scripts plus archived docs under `docs/archive/`; product docs mark the workstream as historical.
  - EmailAgent remains wired for storage/runtime and replay but is explicitly non-truth; StudyAgent is frozen with no new usage added.
  - Tests and CI (via `scripts/test.sh` and `.github/workflows/python-checks-reusable.yml`) now focus on the workflow-engine core, with pytest and rg-based diagnostics used to guard against regressions in deprecated/quarantined paths.
- `.gsd/milestones/M001/M001-SUMMARY.md` captures what was shipped in the kernel milestone and is the primary reference for kernel behavior.

## Architecture / Key Patterns

- Python monorepo with `apps/` (API, worker, Telegram bot) and `packages/` (orchestration, storage, connectors, agents, observability, archived domain).
- DB-first design with Postgres as the source of truth for workflow state, artifacts, sync records, and events.
- Orchestration logic lives in `packages/orchestration/src/helm_orchestration/` and owns workflow semantics, specialist dispatch, approval, sync execution, replay, and status projection.
- Storage models and repositories live in `packages/storage/src/helm_storage/` and implement workflow_* tables and related persistence.
- Connectors (task/calendar) live in `packages/connectors/src/helm_connectors/` and are invoked via adapter contracts.
- Agents (including EmailAgent and StudyAgent) live in `packages/agents/src/helm_agents/`; EmailAgent is deprecated for this version, StudyAgent is frozen.
- Operator surfaces are provided by FastAPI in `apps/api` and Telegram commands in `apps/telegram-bot`, backed by shared status/replay services.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping across M001 and M002.

## Milestone Sequence

- [x] M001: Helm Orchestration Kernel v1 — Durable workflow kernel with a representative weekly scheduling workflow and shared operator surfaces.
- [ ] M002: Helm Truth-Set Cleanup — Strict workflow-engine truth set, aggressive removal of stale/aspirational artifacts, and verified task/calendar workflow protection after cleanup.
  - Working inventory for M002 cleanup and deprecated surfaces: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`.
