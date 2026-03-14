S01: Define Helm workflow-engine truth set

**Goal:** Establish a small, explicit truth note for the current Helm workflow engine and define classification rules (keep/freeze/deprecate/remove/quarantine) grounded in the M001 kernel and weekly scheduling behavior.

**Demo:** A reviewer can open the S01 truth note and S01 plan docs, see exactly what constitutes the workflow-engine truth set and how artifacts will be classified in later slices, and trace R001/R004 to concrete artifacts and rules.

## Must-Haves

- Truth note describing the workflow-engine-centric Helm truth set, including kernel, representative workflow, and operator surfaces.
- Classification rules that define keep/freeze/deprecate/remove/quarantine in terms of this truth set.
- Initial classification inventory tagging major components (agents, connectors, packages, docs, tests) according to these rules.
- Requirements file updated so R001/R004 are clearly mapped to this slice and to the new truth note.

## Verification

- `cat .gsd/milestones/M002/M002-TRUTH-NOTE.md` shows a concise, workflow-engine-centric truth definition aligned with M001 decisions.
- `cat .gsd/REQUIREMENTS.md` shows R001/R004 updated with proof/ownership/traces referencing the truth note and S01 artifacts.
- `cat .gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` shows concrete classification rules and at least one real example for each status.
- `cat .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` shows a first-pass inventory of major modules/docs/tests tagged by status, including EmailAgent/StudyAgent, LinkedIn, Night Runner, and `packages/domain`.

## Observability / Diagnostics

- Runtime signals: n/a (planning/documentation slice; no runtime changes).
- Inspection surfaces: S01 docs under `.gsd/milestones/M002/` (truth note, classification rules, initial inventory) and updated `.gsd/REQUIREMENTS.md`.
- Failure visibility: If future slices cannot decide whether an artifact is truth-defining, the absence or vagueness of classification entries in these files will be the primary signal.
- Redaction constraints: None (no secrets or PII; all artifacts are internal docs and code paths).

## Integration Closure

- Upstream surfaces consumed: `.gsd/milestones/M001/M001-SUMMARY.md`, `.gsd/DECISIONS.md`, `.gsd/PROJECT.md`, existing code/tests in `packages/orchestration`, `packages/storage`, `packages/agents`, `apps/api`, `apps/worker`, `apps/telegram-bot`.
- New wiring introduced in this slice: Cross-links between the truth note, classification docs, and `.gsd/REQUIREMENTS.md` so later slices and requirements can reference a single truth set definition.
- What remains before the milestone is truly usable end-to-end: S02 cleanup that enforces these classifications in the tree and S03 verification that task/calendar workflows still operate correctly post-cleanup.

## Tasks

- [x] **T01: Write workflow-engine truth note and map to requirements** `est:1h`
  - Why: R001/R004 require a small, explicit truth set definition; this task writes the truth note and connects it to requirements so future work treats it as the source of truth.
  - Files: `.gsd/milestones/M002/M002-TRUTH-NOTE.md`, `.gsd/REQUIREMENTS.md`
  - Do: Draft a concise truth note centered on the workflow kernel, representative weekly scheduling workflow, and operator surfaces using M001 summary and `.gsd/DECISIONS.md`; explicitly call out Task/Calendar agents as core and Email/Study as non-core/frozen; update `.gsd/REQUIREMENTS.md` so R001/R004 reference the truth note and this slice as their proof surface.
  - Verify: `cat .gsd/milestones/M002/M002-TRUTH-NOTE.md` and `cat .gsd/REQUIREMENTS.md` show the truth note and updated requirement entries with clear references.
  - Done when: The truth note exists, is internally consistent with M001 decisions, and R001/R004 entries point to it as their primary proof artifact.
- [x] **T02: Define classification rules and agent status treatment** `est:45m`
  - Why: S02/S03 need concrete rules for keep/freeze/deprecate/remove/quarantine and explicit treatment of EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain`.
  - Files: `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`, `.gsd/REQUIREMENTS.md`
  - Do: Write a small classification rules doc that defines each status in terms of the workflow-engine truth set and gives at least one example each; encode how non-core agents and deprecated paths should be treated; update `.gsd/REQUIREMENTS.md` traceability/proof notes for R002/R005 to reference these rules as inputs, even though those requirements are primarily owned by S02.
  - Verify: `cat .gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` shows clear rules and examples; `.gsd/REQUIREMENTS.md` mentions classification rules under R002/R005 notes or proof hints.
  - Done when: The classification rules file exists, covers all statuses, and future slices can use it directly without guessing semantics.
- [x] **T03: Build initial classification inventory for major components** `est:1h`
  - Why: S02 needs a starting inventory of what to keep, freeze, deprecate, remove, or quarantine; S01 should seed this based on the truth note and rules.
  - Files: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`, `.gsd/PROJECT.md`
  - Do: Scan major packages/apps/docs/tests (orchestration, storage, agents, connectors, API/worker/Telegram, LinkedIn, Night Runner, `packages/domain`, key specs/runbooks) and tag each as keep/freeze/deprecate/remove/quarantine per the rules; summarize how EmailAgent and StudyAgent are classified; add a short note to `.gsd/PROJECT.md` that this inventory is the working set for M002 cleanup.
  - Verify: `cat .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` shows tagged entries for all major components; `.gsd/PROJECT.md` references this inventory in the milestone section.
  - Done when: The inventory provides broad coverage of major components (not every file) and clearly reflects the truth note and classification rules.

## Files Likely Touched

- `.gsd/milestones/M002/M002-TRUTH-NOTE.md`
- `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`
- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/PROJECT.md`
- `.gsd/DECISIONS.md` (append only if new structural decisions emerge during planning/execution)