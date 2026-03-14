# M002 / S01 — Research

**Date:** 2026-03-14

## Summary

Slice S01 owns R001 and R004 and supports R002–R003 by defining the current-version Helm truth set around the workflow engine, replay/recovery/approvals, and task/calendar sync protection. The existing codebase already centers these flows in `packages/orchestration`, `packages/storage`, and the worker/API/Telegram surfaces; TaskAgent and CalendarAgent schemas and handlers are wired end-to-end and exercised by unit tests. StudyAgent and EmailAgent live in `packages/agents` and are used by the worker, but their higher-level planning specs are not part of the validated kernel.

Primary recommendation: treat the workflow kernel (orchestration + storage + replay/status services) and the weekly scheduling workflow (TaskAgent + CalendarAgent + sync connectors + API/Telegram/worker wiring) as the only truth-defining surfaces for this milestone. EmailAgent and StudyAgent remain as non-core agents; StudyAgent is explicitly frozen and EmailAgent is in-scope only as a consumer of the kernel. LinkedIn, Night Runner, and `packages/domain` are presumed non-truth until proven otherwise and should be classified as deprecated/remove-candidates in S02 unless concrete runtime dependencies surface in further exploration.

## Recommendation

- Anchor R001 on the orchestration and storage packages plus worker/API/Telegram integration and task/calendar connectors. The truth note should:
  - Describe the kernel’s durable workflow model, replay/recovery/approvals, and sync protection in terms of existing decisions in `.gsd/DECISIONS.md`.
  - Identify TaskAgent and CalendarAgent (schemas + handlers) and their sync connectors as the representative, protected workflow path.
  - Enumerate operator surfaces (API routes, Telegram commands, worker jobs) that meaningfully expose or drive these flows.
- For R004, explicitly classify EmailAgent and StudyAgent as non-core:
  - Keep their implementations and minimal wiring in place.
  - Mark StudyAgent as *frozen* (no new work in M002) and ensure any study-specific specs/docs are treated as historical.
  - Treat email-related planning specs as deprecated truth, even though the underlying agent remains.
- For R005, prepare S02 by:
  - Treating LinkedIn, Night Runner, and `packages/domain` as deprecated/remove-candidates unless research in S02 shows a live dependency.
  - Using imports/tests searches in S02 to prove whether these packages participate in the workflow-engine truth set; default to removal if they do not.
- Use existing unit tests around `TaskAgentInput`/`TaskAgentOutput`, workflow orchestration services, replay services, and worker jobs as the primary technical evidence for what is “truth-defining” vs “aspirational”.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Durable workflow orchestration, replay, approvals, and specialist dispatch | `packages/orchestration` kernel (WorkflowOrchestrationService, replay/status services, schemas) + `packages/storage` workflow_* tables and repositories | Already validated in M001 with hermetic tests and codified decisions; reusing these services preserves behavior and avoids re-implementing workflow semantics in apps or agents. |
| Task and calendar normalization plus sync execution | `TaskAgentInput`/`TaskAgentOutput` schemas in `helm_orchestration.schemas`, Task/Calendar specialists in `packages/agents`, and connectors in `packages/connectors` | These components already define the representative scheduling workflow; they should remain the canonical path for task/calendar flows instead of new ad-hoc orchestrations. |
| Operator-facing workflow status, approval, and replay views | Shared workflow status and replay services plus API/Telegram projections | Decisions explicitly state that API and Telegram share one status projection; duplicating logic in new surfaces risks divergence from the kernel truth set. |

## Existing Code and Patterns

- `packages/orchestration/src/helm_orchestration/schemas.py` — defines `TaskAgentInput`, `TaskAgentOutput`, and related workflow artifacts; these schemas are used by worker jobs and tests and should be treated as canonical for task normalization.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — worker job wiring for workflow runs, including helper `_run_task_agent` that validates payloads as `TaskAgentInput` and returns `TaskAgentOutput`; this file shows how the kernel is driven and how specialists are invoked.
- `tests/unit/test_workflow_orchestration_service.py` — exercises the orchestration service, including TaskAgent payloads and handlers; this test suite is a key reference for the workflow-engine truth set and for R001/R003.
- `tests/unit/test_workflow_status_service.py` and `tests/unit/test_replay_service.py` — validate status projection and replay behavior using TaskAgent schemas; they encode decisions around recovery, replay lineage, and operator surfaces.
- `packages/storage/src/helm_storage/` (workflow_* repositories and models) — implements durable persistence for workflows, steps, artifacts, approvals, and sync records; M001 treated this as truth, and M002 should rely on it rather than introducing alternate storage paths.
- `apps/api`, `apps/telegram-bot`, `apps/worker` roots — define runtime surfaces for workflows; for S01 these are important mainly as pointers to which routes/commands/jobs reflect the kernel truth set.
- `packages/agents/src/helm_agents/` — contains agent implementations including EmailAgent, StudyAgent, TaskAgent, and CalendarAgent; Task/Calendar agents are core, Email/Study are non-core for this milestone.

## Constraints

- The truth set must not contradict validated kernel requirements or decisions — any reclassification must align with `.gsd/DECISIONS.md` and M001’s summaries.
- Task/calendar workflows and their persistence schema are fixed for this milestone; S01 can define truth but not change core behavior.
- LinkedIn, Night Runner, and `packages/domain` are presumed non-core; if they are found to be wired into kernel flows, that wiring must be documented as a risk and handled in S02.
- EmailAgent and StudyAgent must remain intact implementations; S01 can only de-scope their planning/spec artifacts from truth status, not remove the agents themselves.

## Common Pitfalls

- **Over-classifying aspirational artifacts as active truth** — Specs or planning docs around email or study can look authoritative; S01 should treat M001 decisions and kernel tests as the primary truth and classify other planning layers as historical unless they are clearly wired into the representative workflow.
- **Accidentally expanding scope beyond task/calendar** — It’s tempting to treat StudyAgent or email workflows as part of the core; for this milestone, they must be explicitly non-core so that cleanup and verification stay centered on the scheduling workflow.

## Open Risks

- Hidden runtime or test dependencies on underdeveloped packages (for example `packages/domain`) could surface in S02 when removal is attempted; S01 should note these as candidates, not yet removed.
- Some Telegram/API commands or runbooks may reference deprecated workflows; if S01 misclassifies these as active, S02 could retain misleading surfaces.
- StudyAgent may be partially wired into orchestration or storage in ways that are not obvious from top-level scans; misclassifying it could understate its impact on kernel behavior even if it remains frozen.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| SQLAlchemy ORM and Postgres persistence (used by `packages/storage`) | bobmatnyc/claude-mpm-skills@sqlalchemy-orm | available |
| SQLAlchemy + Alembic best practices | wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review | available |
| SQLAlchemy with Postgres specifics | cfircoo/claude-code-toolkit@sqlalchemy-postgres | available |

## Sources

- TaskAgent schemas and worker/test usage (source: in-repo code under `packages/orchestration`, `apps/worker`, and `tests/unit`).
- Storage and requirements context (source: `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, and M002 milestone docs preloaded in this unit).