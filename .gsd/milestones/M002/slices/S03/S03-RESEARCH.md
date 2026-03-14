S03 — Task/calendar workflow protection and verification — Research

**Date:** 2026-03-14

## Summary

This slice sits on top of a cleaned-up truth set (S01) and deprecation/quarantine pass (S02) and is responsible for proving that the representative weekly scheduling / task+calendar workflows still work end-to-end via API, worker, and Telegram. The core behavior is already strongly tested at the kernel and projection layers: the orchestration service, storage repositories, sync/replay services, and workflow status projection all have substantial unit and integration coverage, including approval checkpoints, apply_schedule behavior, sync lineage, recovery classification, and Telegram/API formatting. End-to-end correctness today is largely inferred from these tests and the existing workflow-runs runbook, not from a single UAT script or automated “happy-path” journey that exercises API + worker + Telegram in one flow.

The main work for S03 is therefore not to invent new behavior, but to (1) define a concrete UAT script that can be run after cleanup to exercise create → normalize → proposal → approval → apply_schedule → sync → replay from an operator’s perspective, and (2) tighten or extend tests where they are currently implicit (e.g., request parsing, weekly_request metadata, completion_summary surface, Telegram commands). The risk surface is subtle coupling between email scheduling remnants and the task/calendar workflow, and between non-truth agents and operator diagnostics. Tests currently pass cleanly, but there is no single artifact that a future milestone can run to re-validate task/calendar behavior after further cleanup.

## Recommendation

Treat S03 as a verification and hardening slice, not a feature slice. Concretely:

- Anchor verification around the existing weekly_scheduling workflow and workflow status projection in `apps/api/src/helm_api/services/workflow_status_service.py`, plus the Telegram workflow commands (approval, replay, completion summaries). Do not introduce new workflow types.
- Keep verification layered:
  - **Contract tests** (kernel + status projection + sync/replay): rely on existing unit/integration tests, extending them only where gaps are discovered (e.g., weekly scheduling request parsing edge cases, completion_summary attention items around replay, task/calendar sync counts in recovery scenarios).
  - **Integration tests** for API and Telegram: ensure there are explicit tests that drive the representative scheduling flow via HTTP routes and Telegram command handlers, asserting key invariants from R003 (approval checkpoint behavior, apply_schedule semantics, downstream sync summaries, replay actions).
  - **UAT script**: encode a minimal operator walkthrough in a new `uat.md` under S03 that explains how to start the stack (API, worker, Telegram bot, Postgres), how to create a weekly scheduling run, how to approve/reject/request revision, how to trigger sync and replay, and what to verify via Telegram/API outputs.
- Make task/calendar workflows the protected core: when adding or adjusting tests, prefer assertions on schedule proposal artifacts, sync records, and workflow status projections over incidental email/Study behavior. Keep EmailAgent/StudyAgent usage out of S03’s new tests except where they are already part of the existing test matrix.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Weekly scheduling request parsing and classification of tasks/protected-time/constraints | `parse_weekly_scheduling_request` and related helpers in `apps/api/src/helm_api/services/workflow_status_service.py` | Already encodes the text-to-WeeklySchedulingRequest transformation and warning semantics used in production; new verification should exercise and extend this, not duplicate parsing logic. |
| Workflow orchestration, approval checkpoints, resume semantics | `WorkflowOrchestrationService` in `packages/orchestration/src/helm_orchestration/workflow_service.py` | This service is the kernel truth for step transitions and approval handling; tests should treat it as the unit under test rather than re-implementing step logic in helpers or fixtures. |
| Sync/replay classification and safe-next-actions | Sync repositories and replay service in `packages/orchestration` and `packages/storage` | Recovery and replay semantics are already centralized; verification should assert on their projections (sync counts, recovery_class, safe_next_actions) instead of hand-rolled status flags. |
| Operator-facing workflow status and completion summaries | `WorkflowStatusService` in `apps/api/src/helm_api/services/workflow_status_service.py` | This projection underlies both API and Telegram surfaces; rely on its `_completion_summary`, `_sync_projection`, and `_approval_projection` instead of new ad-hoc projections. |
| Telegram operator commands for workflows and tasks | `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` and `.../services/command_service.py` | These layers already format workflow status and scheduled task lists; UAT and tests should exercise them rather than bypassing Telegram semantics. |

## Existing Code and Patterns

- `apps/api/src/helm_api/services/workflow_status_service.py` — Central workflow status projection, including run creation (`build_workflow_run_create_input`), weekly scheduling request parsing, schedule proposal projection, sync projection, failure classification, and `completion_summary` construction for `weekly_scheduling` runs. This file effectively defines the operator-facing contract that S03 must protect; tests and UAT should assert on its outputs rather than re-deriving summaries.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` — Orchestration kernel managing run creation, step advancement (including `dispatch_task_agent`, `await_schedule_approval`, and `apply_schedule`), approval checkpoints, and replay. Unit tests in `tests/unit/test_workflow_orchestration_service.py` already cover schedule proposal creation, approval behavior, and apply_schedule semantics; S03 should lean on these tests and extend them if specific R003 invariants are missing.
- `packages/storage/src/helm_storage/models.py` and `.../repositories` — Workflow tables (`workflow_runs`, `workflow_steps`, `workflow_artifacts`, `workflow_sync_records`, `workflow_approval_checkpoints`) and repositories. Tests in `tests/unit/test_workflow_repositories.py` validate linkage between schedule proposals, approval checkpoints, and sync lineage; these form part of the contract that must remain stable after cleanup.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — Worker job wiring for workflow execution, including the schedule proposal validator and the apply_schedule step. Integration tests (`tests/integration/test_workflow_status_routes.py`, `tests/integration/test_workflow_status_service.py`) exercise these via API + worker semantics; S03 verification should confirm that worker behavior remains aligned with API status projections.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` — Telegram commands for listing workflows, showing completion summaries, and replay-related actions. Unit tests (`tests/unit/test_workflow_telegram_commands.py`, `tests/unit/test_telegram_commands.py`) already assert on `apply_schedule` step naming and completion headlines; S03 can extend these to cover any gaps discovered in completion summary or replay messaging.
- `docs/runbooks/workflow-runs.md` — Existing runbook for manually exercising workflow runs, including schedule proposal inspection, approval, apply_schedule verification, and restart-safe behavior. This is the closest thing to a UAT script today; S03’s UAT document should reference and potentially compress this into a smaller, scheduling-focused flow.

## Constraints

- **Truth-set constraints:** The only truth-defining workflow for M002 is `weekly_scheduling`; S03 must not add new workflow types or treat Email/Study flows as core. TaskAgent and CalendarAgent are the only truth-defining agents; EmailAgent is deprecated and StudyAgent is frozen.
- **Cleanup constraints:** `packages/domain` has been quarantined and must not be reintroduced into the runtime import graph. Night Runner remains deprecated and out-of-scope. LinkedIn remains purely conceptual.
- **Operational constraints:** Telegram and API remain the primary operator surfaces; no new dashboard/UI should be introduced in this slice. Verification must rely on these surfaces plus the worker, not on new orchestration paths.
- **Testing constraints:** The existing pytest suite (`uv run --frozen --extra dev pytest -q tests/unit tests/integration`) is green and needs to stay that way. New tests must work with the current Postgres schema and not broaden truth status for Email/Study.

## Common Pitfalls

- **Accidentally elevating Email/Study flows to truth-defining status** — Adding new tests or docs that treat EmailAgent or StudyAgent workflows as canonical examples would contradict the M002 truth note. Keep S03 focused on weekly scheduling; if Email/Study wiring appears in tests, treat it as auxiliary coverage only.
- **Over-specifying completion summaries based on current string formats** — API and Telegram completion headlines are user-facing strings; tests should assert on core semantics (e.g., counts of blocks and writes, presence of replay/recovery cues) rather than brittle full-string equality whenever possible, to avoid locking in incidental phrasing.

## Open Risks

- The current tests and runbooks validate kernel and projection behavior, but there is no single UAT script that walks an operator through the full weekly scheduling loop via API + Telegram. Without this, future cleanup passes might accidentally break end-to-end flows while leaving unit tests green.
- Subtle dependencies on non-truth agents (especially EmailAgent’s scheduled tasks and digest jobs) might still exist in operator workflows or scripts; S03 must be careful not to conflate email scheduling with the core task/calendar scheduling workflow.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI (API layer) | wshobson/agents@fastapi-templates | available |
| Postgres (workflow storage) | supabase/agent-skills@supabase-postgres-best-practices | available |
| Telegram Bot (operator surface) | claude-office-skills/skills@telegram-bot | available |

## Sources

- Existing kernel and status projection behavior, including weekly scheduling request parsing, proposal/version handling, sync projection, and completion summaries (source: `apps/api/src/helm_api/services/workflow_status_service.py` plus associated tests under `tests/unit` and `tests/integration`).
- Truth-set framing, agent classification, and cleanup guarantees from M002 S01/S02 (source: `.gsd/milestones/M002/M002-TRUTH-NOTE.md`, `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`, S01/S02 summaries).
- Repository layout and existing worker/API/Telegram job wiring for workflows (source: `apps/worker`, `apps/api`, `apps/telegram-bot`, and `docs/runbooks/workflow-runs.md`).
