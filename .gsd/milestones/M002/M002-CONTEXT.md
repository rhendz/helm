# M002: Helm Truth-Set Cleanup — Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

## Project Description

Helm is a single-user internal AI system centered on the Helm Orchestration Kernel: a durable workflow engine that runs multi-step workflows with typed specialist dispatch, durable artifacts, approval-gated side effects, restart-safe resume, replay-aware recovery, and shared operator surfaces across API and Telegram.

M001 shipped the kernel proof via a representative weekly scheduling workflow that exercises task and calendar specialists, approval checkpoints, outbound sync with recovery/replay, and shared operator surfaces. The repo now contains kernel code, adapters, agents, tests, docs, and historical planning artifacts from earlier Helm explorations.

## Why This Milestone

The repo contains stale specs, deprecated integrations, historical planning artifacts, underdeveloped packages (for example `packages/domain`), and tests/docs that no longer represent the current product but still appear as "possibility" to future iterations. These artifacts can mislead GSD planning, encode deprecated architecture, and cause new work to build on dead paths.

M002 exists to establish a sharp current-version truth set for Helm, centered on the workflow engine and its task/calendar flows, and to aggressively remove or quarantine misleading context so future milestones do not inherit stale decisions by default.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Read a small current-version truth note and see exactly which parts of Helm are active, frozen, deprecated, or remove-candidates.
- Inspect a list of delete/archive candidates and a cleanup plan that future milestones can safely build on, knowing which tests/CI checks no longer define scope.

### Entry point / environment

- Entry point: repo and docs (`.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, M002 truth note, milestone/slice docs), plus existing Helm workflows.
- Environment: local dev (existing Docker/Make targets, pytest), with Telegram/API/worker surfaces available as in M001.
- Live dependencies involved: Postgres database, worker, API, Telegram bot for task/calendar workflow verification.

## Completion Class

- Contract complete means: Active vs frozen vs deprecated vs remove classifications are written down, requirements updated, and a truth note plus cleanup plan exist that describe the current-version Helm workflow-engine truth set.
- Integration complete means: After cleanup and deprecation changes, the existing task/calendar workflow flows still operate correctly through API/worker/Telegram surfaces.
- Operational complete means: None beyond existing M001 guarantees; this milestone must not degrade worker/API/Telegram lifecycle behavior.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- The weekly scheduling / task+calendar workflow still runs end-to-end (create → normalize → proposal → approval → sync → completion → replay/recovery) after truth-set cleanup.
- Telegram/API/worker surfaces for that workflow continue to function as in M001 (status, approval, replay, lineage), with no regressions introduced by removal/quarantine work.
- The small truth note, requirement updates, and classification lists accurately reflect what remains in the repo; there is no major stale or aspirational surface left that could reasonably mislead a future GSD run.

## Risks and Unknowns

- Misclassification of artifacts — accidentally deleting or de-scoping something that is required for the current workflow-engine truth set could silently break behavior or erase necessary reference material.
- Hidden dependencies from tests or CI on deprecated architecture — some tests or checks may still encode old email/LinkedIn/Night Runner paths and fail in non-obvious ways when removed.
- Underdeveloped packages (for example `packages/domain`) and one-off abstractions may be partially wired; removing them may surface missing seams that need explicit documentation.
- Task/calendar flows may depend on historical assumptions in docs or runbooks; cleaning those up without re-verifying flows could regress operator confidence.

## Existing Codebase / Prior Art

- `.gsd/milestones/M001/M001-SUMMARY.md` — authoritative summary of the kernel, weekly scheduling workflow, and operator surfaces.
- `.gsd/DECISIONS.md` — append-only register of workflow-kernel decisions that define current behavior.
- `.gsd/REQUIREMENTS.md` — current capability contract, including validated kernel requirements and active follow-on requirements (additional specialists, workflows, coordination).
- `packages/orchestration/src/helm_orchestration/` — kernel orchestration, resume, validators, schemas, and replay services.
- `packages/storage/src/helm_storage/` — workflow_* tables, repositories, and migrations.
- `apps/api`, `apps/worker`, `apps/telegram-bot` — runtime surfaces that exercise the kernel for weekly scheduling and task/calendar flows.
- `packages/connectors/src/helm_connectors/task_system.py` and `calendar_system.py` — task and calendar adapter stubs used by the representative workflow.
- `packages/agents/src/helm_agents/` — agent implementations including EmailAgent and StudyAgent.
- `packages/domain/src/helm_domain/` — underdeveloped aspirational domain layer that should not define truth unless concretely required.

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- REQ-DURABLE-PERSISTENCE — already validated in M001; this milestone must preserve it while cleaning stale context.
- REQ-SPECIALIST-DISPATCH — validated in M001; task/calendar specialist dispatch must remain intact.
- REQ-REPRESENTATIVE-WORKFLOW — validated in M001; the representative weekly scheduling workflow must remain intact.
- REQ-OPERATOR-SURFACES — validated in M001; API/Telegram operator surfaces must keep working for task/calendar workflows.

## Scope

### In Scope

- Define the current-version Helm truth set centered on the workflow engine, replay/recovery/approvals, and task/calendar sync protection.
- Classify repo artifacts (code, tests, docs, runbooks, specs, planning notes) as active, frozen, deprecated, or remove-candidates.
- Explicitly mark StudyAgent as frozen (real surface, outside this version's iteration scope).
- Explicitly deprecate LinkedIn and Night Runner and remove their code/docs where possible.
- Remove Helm-level email planning/spec/program artifacts as canonical truth while leaving EmailAgent code untouched.
- Aggressively identify and physically remove misleading or aspirational layers (for example `packages/domain` and similar one-off abstractions) that are not required for the current truth set.
- Identify and remove or quarantine tests/CI checks that preserve deprecated architecture or non-core flows.
- Produce a cleanup plan and lists (classification, delete/archive/test-governance changes) that future milestones can build on.

### Out of Scope / Non-Goals

- Refactoring or expanding EmailAgent behavior beyond what's needed to keep current flows working.
- Extending StudyAgent behavior or adding new study workflows in this milestone.
- Introducing new workflow types beyond what's required to verify cleanup.
- Changing core kernel semantics, persistence schema, or approval/replay contracts.
- Adding new primary dashboards or UI surfaces beyond existing Telegram/API.

## Technical Constraints

- Current-version truth is centered on Helm core, not on any single agent vertical.
- Core truth set for this version:
  - durable workflow engine
  - replay / recovery / approvals
  - task/calendar sync protection
  - Telegram / API / worker runtime surfaces that support those flows
- Task/calendar workflow behavior must still work after cleanup; verification/UAT around these flows is mandatory.
- EmailAgent and StudyAgent both remain present, but neither defines the current-version truth set.
- Bias toward physical removal of underdeveloped, non-canonical, and aspirational layers; quarantine only when a concrete, documented reason exists.

## Integration Points

- Postgres — workflow_* tables and any additional tables touched by cleanup.
- API/worker — workflows, replay, and sync jobs that must remain functional after artifact removal.
- Telegram — operator commands for workflows that must keep working for task/calendar flows.

## Open Questions

- How many existing tests/CI checks meaningfully protect the workflow-engine truth set versus encoding deprecated architecture?
- Are there any subtle task/calendar workflow dependencies on currently "aspirational" layers (for example `packages/domain`) that need to be documented before removal?
