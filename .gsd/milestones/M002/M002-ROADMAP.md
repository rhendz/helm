# M002: Helm Truth-Set Cleanup

**Vision:** Establish a strict, current-version Helm truth set centered on the workflow engine and task/calendar flows, aggressively remove or de-scope stale and aspirational artifacts, and prove that task/calendar workflows still operate correctly after cleanup.

## Success Criteria

- The current-version Helm truth set is written down in a small truth note and reflected in requirements and classifications.
- Repo artifacts (code, docs, specs, tests, runbooks) are classified as active, frozen, deprecated, or remove-candidates, with a bias toward physical removal of non-truth surfaces.
- LinkedIn, Night Runner, and underdeveloped aspirational layers (for example `packages/domain`) are explicitly deprecated and removed or quarantined with clear rationale.
- EmailAgent and StudyAgent remain present but are not treated as truth-defining for this version; StudyAgent is frozen.
- Task/calendar workflows (weekly scheduling) still run end-to-end via API/worker/Telegram after cleanup, with explicit verification/UAT.

## Key Risks / Unknowns

- Misclassifying artifacts and deleting something that is required for the current workflow-engine truth set.
- Hidden dependencies in tests/CI or runtime wiring on deprecated or aspirational modules.
- Underdeveloped packages (for example `packages/domain`) being partially wired in ways that are not obvious from a quick scan.
- Workflow verification missing a subtle regression in task/calendar behavior after cleanup.

## Proof Strategy

- Misclassification risk → retire in **S01** by grounding the truth set in M001 summaries, decisions, and existing workflow kernel surfaces, and by producing an explicit truth note and classification rules.
- Hidden dependency risk → retire in **S02** by systematically scanning imports/tests/CI for deprecated/aspirational paths, documenting dependencies before removal, and updating or removing tests accordingly.
- Task/calendar regression risk → retire in **S03** by running targeted tests and manual/UAT scripts before and after cleanup, verifying weekly scheduling flows via API/Telegram/worker.

## Verification Classes

- Contract verification: pytest suites covering workflow kernel, task/calendar specialists, and status/replay behavior; static checks that classification lists and truth note exist and reference live code.
- Integration verification: running weekly scheduling workflows end-to-end against local Postgres with worker/API/Telegram surfaces.
- Operational verification: basic restart-safe behavior as established in M001; ensure cleanup does not introduce new long-running or lifecycle issues.
- UAT / human verification: a short script to exercise task/calendar workflows (create, approve, replay) after cleanup and visually confirm expected behavior.

## Milestone Definition of Done

This milestone is complete only when all are true:

- The current-version Helm truth set is captured in a small note and reflected in `.gsd/REQUIREMENTS.md` and M002 docs.
- Repo artifacts are classified as active, frozen, deprecated, or remove-candidates, with concrete lists for deletion/archival.
- LinkedIn, Night Runner, and underdeveloped aspirational layers (including `packages/domain` if not required) are deprecated and removed or quarantined with explicit rationale.
- EmailAgent and StudyAgent are present but clearly not truth-defining; StudyAgent is marked frozen.
- Weekly scheduling / task+calendar workflows still run end-to-end via API/worker/Telegram, proven by tests and a UAT script written into M002 slice docs.
- The cleanup plan (lists of delete/archive candidates and tests/CI checks that should stop governing future work) exists and is referenced from `.gsd/PROJECT.md` and M002 docs.

## Requirement Coverage

- Covers: R001, R002, R003, R004, R005
- Partially covers: R020 (by setting the stage for additional workflows)
- Leaves for later: R020 (fully), and any new workflow-expansion requirements.
- Orphan risks: None expected after S03 if verification is adequate.

## Slices

- [x] **S01: Define Helm workflow-engine truth set** `risk:high` `depends:[]`
  > After this: there is a small current-version truth note and explicit classification rules (keep/freeze/deprecate/remove/quarantine) grounded in M001’s kernel and weekly scheduling behavior, plus initial tagging of major components (agents, connectors, packages, docs, tests).

- [x] **S02: Repo cleanup and deprecation enforcement** `risk:medium` `depends:[S01]`
  > After this: stale, misleading, or aspirational artifacts (including LinkedIn, Night Runner, `packages/domain`, legacy specs/docs/tests) are physically removed or quarantined with explicit rationale, and tests/CI checks that no longer protect the core truth set are updated or removed.

- [x] **S03: Task/calendar workflow protection and verification** `risk:high` `depends:[S01,S02]`
  > After this: weekly scheduling / task+calendar workflows are verified to run end-to-end via API/worker/Telegram after cleanup, with a documented UAT script and any necessary test adjustments to treat these flows as the protected core.

## Boundary Map

### S01 → S02

Produces:
- `.gsd/milestones/M002/M002-TRUTH-NOTE.md` (or equivalent) — small current-version Helm truth note describing the workflow-engine-centric truth set and agent status (active/frozen/deprecated).
- Updated `.gsd/REQUIREMENTS.md` — active requirements R001–R005 mapped to M002 slices.
- Initial classification inventory — a structured list (e.g., in M002 docs) of major modules/packages/docs/tests tagged as keep/freeze/deprecate/remove/quarantine.

Consumes:
- `.gsd/milestones/M001/M001-SUMMARY.md` — kernel and weekly scheduling summary.
- `.gsd/DECISIONS.md` — existing architectural decisions.
- `.gsd/PROJECT.md` — project description and current state.

### S02 → S03

Produces:
- Applied cleanup changes in the repo: removed or quarantined code/docs/tests for deprecated or aspirational paths (LinkedIn, Night Runner, underdeveloped domain layers, stale specs/runbooks).
- Updated classification inventory listing what was kept, frozen, deprecated+removed, or quarantined, with rationale where quarantine is chosen.
- A list of tests/CI checks that were removed or updated and a list of remaining tests that explicitly protect the workflow-engine truth set.

Consumes from S01:
- Truth note and classification rules.
- Initial classification inventory for targeting cleanup.

### S03 → (future milestones)

Produces:
- Verified task/calendar workflow behavior after cleanup, with explicit notes on how it was tested (pytest files, runbook steps, Telegram/API commands).
- A UAT script (`uat.md` in S03 slice) that future milestones can reuse to quickly confirm task/calendar workflows still operate.
- Finalized cleanup plan and classification lists referenced from `.gsd/PROJECT.md` and future milestone context.

Consumes from S01 and S02:
- Truth note and classification inventories.
- Applied cleanup changes (removed/quarantined artifacts).
- Updated test suite and CI configuration.
