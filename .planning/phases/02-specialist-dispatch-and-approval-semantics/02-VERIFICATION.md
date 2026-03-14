---
phase: 02-specialist-dispatch-and-approval-semantics
verified: 2026-03-14T00:00:00Z
status: passed
score: 4/4 must-haves verified
---

# Phase 2: Specialist Dispatch And Approval Semantics Verification Report

**Phase Goal:** Helm can execute typed `TaskAgent` and `CalendarAgent` steps, create approval checkpoints, support revision versioning, and resume from decisions safely.
**Verified:** 2026-03-14T00:00:00Z
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Helm invokes `TaskAgent` and `CalendarAgent` through a shared typed kernel contract with invocation records. | ✓ VERIFIED | Specialist payload schemas, semantic step registration, and invocation persistence are implemented in [schemas.py](/Users/ankush/git/helm/packages/orchestration/src/helm_orchestration/schemas.py), [workflow_service.py](/Users/ankush/git/helm/packages/orchestration/src/helm_orchestration/workflow_service.py), and [workflow_specialist_invocations.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/repositories/workflow_specialist_invocations.py). Covered by `tests/unit/test_workflow_orchestration_service.py`, `tests/unit/test_workflow_repositories.py`, and `tests/unit/test_worker_registry.py`. |
| 2 | Helm pauses before downstream create, update, or delete actions and records an approval request as durable workflow state. | ✓ VERIFIED | Approval checkpoints and blocked run semantics are implemented in [workflow_service.py](/Users/ankush/git/helm/packages/orchestration/src/helm_orchestration/workflow_service.py), [models.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/models.py), and [workflow_approval_checkpoints.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/repositories/workflow_approval_checkpoints.py). Covered by orchestration, route, and Telegram command tests. |
| 3 | User can approve, reject, or request revision, and the workflow resumes from the correct step. | ✓ VERIFIED | Shared kernel decision semantics are exercised by [approve.py](/Users/ankush/git/helm/apps/telegram-bot/src/helm_telegram_bot/commands/approve.py), [workflow_runs.py](/Users/ankush/git/helm/apps/api/src/helm_api/routers/workflow_runs.py), and `tests/unit/test_workflow_orchestration_service.py` plus `tests/integration/test_workflow_status_routes.py`. |
| 4 | Revised proposals are stored as new artifact versions with inspectable decision lineage. | ✓ VERIFIED | Proposal supersession and revision-linked lineage are implemented in [workflow_artifacts.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/repositories/workflow_artifacts.py), [workflow_service.py](/Users/ankush/git/helm/packages/orchestration/src/helm_orchestration/workflow_service.py), and exposed in [workflow_status_service.py](/Users/ankush/git/helm/apps/api/src/helm_api/services/workflow_status_service.py). Covered by unit, Telegram, and integration versioning tests. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| [specialist dispatch migration](/Users/ankush/git/helm/migrations/versions/20260313_0008_specialist_dispatch.py) | Durable specialist invocation persistence | ✓ EXISTS + SUBSTANTIVE | Adds the invocation storage used to tie typed specialist execution to runs, steps, and artifacts. |
| [approval checkpoint migration](/Users/ankush/git/helm/migrations/versions/20260313_0009_approval_checkpoints.py) | Durable approval pause and decision storage | ✓ EXISTS + SUBSTANTIVE | Adds approval checkpoint state and resume metadata required for blocked approval flows. |
| [workflow service](/Users/ankush/git/helm/packages/orchestration/src/helm_orchestration/workflow_service.py) | Kernel-owned specialist, approval, and revision semantics | ✓ EXISTS + SUBSTANTIVE | Executes typed specialists, creates approval checkpoints, applies decisions, and creates revised proposal versions. |
| [shared status service](/Users/ankush/git/helm/apps/api/src/helm_api/services/workflow_status_service.py) | Shared API/Telegram projection for approval checkpoints and proposal versions | ✓ EXISTS + SUBSTANTIVE | Projects latest proposal, checkpoint actions, prior versions, and decision lineage consistently. |
| [Telegram approval commands](/Users/ankush/git/helm/apps/telegram-bot/src/helm_telegram_bot/commands/approve.py) | Thin operator actions over kernel semantics | ✓ EXISTS + SUBSTANTIVE | Exposes approve, reject, and request-revision commands that target concrete proposal artifact ids. |

**Artifacts:** 5/5 verified

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| [resume_service.py](/Users/ankush/git/helm/packages/orchestration/src/helm_orchestration/resume_service.py) | [workflow worker job](/Users/ankush/git/helm/apps/worker/src/helm_worker/jobs/workflow_runs.py) | Semantic specialist dispatch by `(workflow_type, step_name)` | ✓ WIRED | Worker execution delegates typed specialist progression through the orchestration-owned registry. |
| [workflow_service.py](/Users/ankush/git/helm/packages/orchestration/src/helm_orchestration/workflow_service.py) | [workflow_approval_checkpoints.py](/Users/ankush/git/helm/packages/storage/src/helm_storage/repositories/workflow_approval_checkpoints.py) | Durable approval pause, decision, and resume linkage | ✓ WIRED | Approval checkpoints are persisted and resolved through storage-backed kernel semantics, not app-layer shortcuts. |
| [workflow_status_service.py](/Users/ankush/git/helm/apps/api/src/helm_api/services/workflow_status_service.py) | [Telegram workflow status wrapper](/Users/ankush/git/helm/apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py) | Shared approval/version read model | ✓ WIRED | Telegram and API use the same checkpoint and proposal-version projection, keeping action semantics aligned. |

**Wiring:** 3/3 connections verified

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AGNT-01 | 02-01 | Helm can invoke `TaskAgent` with typed input derived from raw workflow input. | ✓ SATISFIED | Specialist input schemas and orchestration tests in `tests/unit/test_workflow_orchestration_service.py`. |
| AGNT-02 | 02-01 | Helm can invoke `CalendarAgent` with typed scheduling input derived from validated task artifacts. | ✓ SATISFIED | Typed calendar dispatch and persisted proposal coverage in `tests/unit/test_workflow_orchestration_service.py`. |
| AGNT-03 | 02-01 | Helm persists invocation records for each specialist execution. | ✓ SATISFIED | Invocation repository and lineage coverage in `tests/unit/test_workflow_repositories.py` and `tests/unit/test_worker_registry.py`. |
| ARTF-04 | 02-01, 02-03 | Helm persists schedule proposal artifacts with lineage and versioning. | ✓ SATISFIED | Proposal artifact persistence and supersession coverage in `tests/unit/test_workflow_repositories.py`, `tests/unit/test_workflow_orchestration_service.py`, and `tests/integration/test_workflow_status_routes.py`. |
| APRV-01 | 02-02 | Helm pauses before downstream side effects. | ✓ SATISFIED | Approval-blocked run and checkpoint creation coverage in `tests/unit/test_workflow_orchestration_service.py`. |
| APRV-02 | 02-02 | User can approve, reject, or request revision for a pending checkpoint. | ✓ SATISFIED | API and Telegram decision routes/commands covered by `tests/integration/test_workflow_status_routes.py` and `tests/unit/test_telegram_commands.py`. |
| APRV-03 | 02-02 | Helm persists the approval request, allowed actions, final decision, and timestamp. | ✓ SATISFIED | Approval persistence and decision-lineage coverage in `tests/unit/test_workflow_orchestration_service.py` and `tests/unit/test_workflow_status_service.py`. |
| APRV-04 | 02-02 | Helm resumes the paused workflow from the correct step after approval, rejection, or revision. | ✓ SATISFIED | Kernel resume semantics covered by `tests/unit/test_workflow_orchestration_service.py` and route tests. |
| APRV-05 | 02-03 | Revised proposals are stored as new artifact versions rather than overwriting prior proposals. | ✓ SATISFIED | Revision-linked proposal version creation covered by `tests/unit/test_workflow_orchestration_service.py`. |
| APRV-06 | 02-03 | User can inspect which proposal version was approved, rejected, or superseded. | ✓ SATISFIED | Latest-first version projections and explicit artifact targeting covered by `tests/unit/test_workflow_status_service.py`, `tests/unit/test_telegram_commands.py`, and `tests/integration/test_workflow_status_routes.py`. |
| DEMO-02 | 02-01 | Helm converts the weekly scheduling request into normalized task artifacts through `TaskAgent`. | ✓ SATISFIED | Representative specialist flow covered by `tests/unit/test_workflow_orchestration_service.py`. |
| DEMO-03 | 02-01 | Helm converts normalized tasks into a schedule proposal through `CalendarAgent`. | ✓ SATISFIED | Representative schedule proposal creation covered by orchestration and repository tests. |

**Coverage:** 12/12 requirements satisfied

## Anti-Patterns Found

None. The Phase 2 shipped scope does not rely on Telegram-only decision semantics, in-place proposal mutation, or ephemeral approval state.

## Human Verification Required

None. The phase goal and mapped requirements are covered by passing storage, orchestration, API, Telegram, and integration tests. The runbook in [workflow-runs.md](/Users/ankush/git/helm/docs/runbooks/workflow-runs.md) remains useful for operator walkthroughs, but it is not a blocker for milestone verification.

## Gaps Summary

**No gaps found.** Phase goal achieved. Ready for milestone audit.

## Verification Metadata

**Verification approach:** Goal-backward from the Phase 2 roadmap goal and success criteria  
**Must-haves source:** [ROADMAP.md](/Users/ankush/git/helm/.planning/ROADMAP.md), [02-01-SUMMARY.md](/Users/ankush/git/helm/.planning/phases/02-specialist-dispatch-and-approval-semantics/02-01-SUMMARY.md), [02-02-SUMMARY.md](/Users/ankush/git/helm/.planning/phases/02-specialist-dispatch-and-approval-semantics/02-02-SUMMARY.md), [02-03-SUMMARY.md](/Users/ankush/git/helm/.planning/phases/02-specialist-dispatch-and-approval-semantics/02-03-SUMMARY.md)  
**Automated checks:** `92` passed, `0` failed  
**Human checks required:** `0`  
**Verification commands run:** `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_worker_registry.py tests/integration/test_workflow_status_routes.py`

---
*Verified: 2026-03-14T00:00:00Z*
*Verifier: Codex*
