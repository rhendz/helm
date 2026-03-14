# S01: Define Helm workflow-engine truth set — UAT

**Milestone:** M002
**Written:** 2026-03-13

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 is a documentation and contract slice that does not change runtime behavior. Its success criteria are the presence and coherence of truth/classification docs and their wiring into requirements and project metadata; these can be fully verified by inspecting repo artifacts.

## Preconditions

- Repo is checked out at the M002 branch with S01 tasks completed.
- No services need to be running; tests/workers are not required for this slice.
- `.gsd/REQUIREMENTS.md`, `.gsd/PROJECT.md`, and the M002 milestone docs are present in the tree.

## Smoke Test

Open the key S01 artifacts and confirm they exist and read coherently:

1. Run:
   - `cat .gsd/milestones/M002/M002-TRUTH-NOTE.md`
   - `cat .gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`
   - `cat .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`
2. **Expected:** All three files exist, render as structured Markdown (no obvious TODO placeholders), and clearly reference each other and the M001 kernel / weekly scheduling workflow.

## Test Cases

### 1. Truth note presence and alignment with requirements

1. Open `.gsd/milestones/M002/M002-TRUTH-NOTE.md` and skim the "Truth-Defining Kernel", "Representative Workflow Truth", "Operator Surfaces In Scope", and "Core vs Non-Core Agents" sections.
2. Open `.gsd/REQUIREMENTS.md` and locate R001 and R004.
3. **Expected:**
   - The truth note explicitly identifies the M001 kernel and representative weekly scheduling workflow as the behavioral truth, and treats TaskAgent/CalendarAgent as core while marking EmailAgent/StudyAgent as non-core (with StudyAgent frozen).
   - R001 and R004 have `Validation: proofed` and their Notes explicitly reference `.gsd/milestones/M002/M002-TRUTH-NOTE.md` as the proof surface.
   - The wording of R001/R004 is consistent with the truth note (no contradictions about what defines Helm or which agents are core).

### 2. Classification rules coverage and agent/integration treatment

1. Open `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`.
2. Locate the status definition sections for `keep`, `freeze`, `deprecate`, `remove`, and `quarantine`.
3. Locate the "Agent and Integration Treatment" section.
4. **Expected:**
   - Each status has a definition, criteria, behavioral rules, and at least one concrete example.
   - The agent/integration treatment section assigns:
     - TaskAgent and CalendarAgent → keep.
     - EmailAgent → deprecate (with remove/quarantine in S02).
     - StudyAgent → freeze.
     - LinkedIn integrations → deprecate.
     - Night Runner / cron-like flows → deprecate.
     - `packages/domain` → quarantine by default.
   - `.gsd/REQUIREMENTS.md` entries for R002 and R005 mention `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` in their Notes as the input for cleanup and deprecated-path handling.

### 3. Classification inventory coverage of major components

1. Open `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`.
2. Inspect the "Kernel and Orchestration", "Agents and Connectors", "Domain Layer", "Operator Surfaces (Apps)", "Docs and Specs", and "Tests" sections.
3. **Expected:**
   - Each major area of the repo is represented (storage/orchestration/runtime/observability, agents/connectors, domain, LLM, apps, docs, tests, misc).
   - EmailAgent, StudyAgent, LinkedIn connectors, Night Runner (if present), and `packages/domain` all appear with statuses matching the classification rules (EmailAgent deprecate, StudyAgent freeze, LinkedIn deprecate, Night Runner deprecate, `packages/domain` quarantine).
   - Rationales for statuses reference the truth note and/or classification rules.

### 4. Project wiring to the classification inventory

1. Open `.gsd/PROJECT.md` and navigate to the "Milestone Sequence" section.
2. **Expected:**
   - The M002 milestone line exists.
   - Under M002, there is a sub-point referencing `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` as the working inventory for M002 cleanup.
   - The "Current State" section acknowledges that older agents/integrations and domain layers exist and need cleanup; this description is consistent with the truth note and inventory.

### 5. Milestone roadmap reflects S01 completion

1. Open `.gsd/milestones/M002/M002-ROADMAP.md`.
2. Find the S01 slice entry.
3. **Expected:**
   - The S01 line is marked `[x]` (completed).
   - The S01 description matches what was actually delivered: a truth note, classification rules, and initial classification inventory.
   - S02 and S03 remain unchecked.

## Edge Cases

### Ambiguous component classification

1. Scan `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` for any major component you know exists in the repo but that feels hard to classify (for example, a connector or doc that participates in multiple flows).
2. Cross-check its status against the classification rules file.
3. **Expected:**
   - The chosen status is justifiable under the rules (keep/freeze/deprecate/remove/quarantine criteria).
   - If the rationale is thin, it at least points back to the truth note and rules, giving S02 clear guidance on how to revisit it.

## Failure Signals

- Any of the three core docs are missing or obviously incomplete (TODOs, placeholder text, or contradictions with M001/M002 descriptions).
- R001 or R004 in `.gsd/REQUIREMENTS.md` are not marked `Validation: proofed` or do not reference the truth note.
- R002 or R005 do not mention the classification rules doc as an input for cleanup.
- Classification inventory omits key components (TaskAgent, CalendarAgent, EmailAgent, StudyAgent, LinkedIn, Night Runner, `packages/domain`) or assigns statuses that contradict the classification rules.
- `.gsd/PROJECT.md` does not reference the classification inventory under M002 or still implies that historical agents/integrations define current truth.
- `.gsd/milestones/M002/M002-ROADMAP.md` still shows S01 as `[ ]`.

## Requirements Proved By This UAT

- R001 — Helm workflow-engine truth set is sharply defined: truth note exists, is coherent, and is wired into `.gsd/REQUIREMENTS.md` as the proof surface.
- R004 — Non-core agents do not define current truth: non-core agent treatment (EmailAgent deprecated, StudyAgent frozen) is explicit in the truth note and classification rules and is reflected in requirements notes.
- R002 — Repo working set reduced to active and frozen truth: partially proved; classification rules and initial inventory exist as inputs for S02, but physical cleanup and validation remain for later slices.
- R005 — Deprecated paths clearly marked and removed where safe: partially proved; deprecated paths (LinkedIn, Night Runner, `packages/domain`, EmailAgent) are tagged and described, but removal/quarantine is deferred to S02.

## Not Proven By This UAT

- R003 — Task/calendar workflows remain intact and verified after cleanup: no runtime behavior or tests are executed in this slice; this remains the responsibility of S03.
- Any performance, operational, or restart-safety properties beyond what M001 previously validated.
- That all deprecated/non-truth artifacts are safe to remove; S02 still needs to scan imports, runtime wiring, and CI configuration before deletion.

## Notes for Tester

- This UAT is intentionally artifact-driven; treat it as a structured sanity check that the truth set and classification contract are written down and coherent before cleanup begins.
- If you find contradictions between the truth note and existing code/docs, prefer the truth note and record the conflict for S02 to resolve via code and documentation changes.
- When in doubt about a classification decision, note it in the M002 classification inventory rather than silently changing behavior; S02 is the slice that should move items between statuses after deeper analysis.