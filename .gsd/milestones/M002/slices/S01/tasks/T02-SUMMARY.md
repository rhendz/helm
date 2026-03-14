---
id: T02
parent: S01
milestone: M002
provides:
  - Classification rules for keep/freeze/deprecate/remove/quarantine grounded in the M002 workflow-engine truth set, plus requirement hints for cleanup slices.
key_files:
  - .gsd/milestones/M002/M002-CLASSIFICATION-RULES.md
  - .gsd/REQUIREMENTS.md
key_decisions:
  - Use a workflow-engine-centric definition of statuses (keep/freeze/deprecate/remove/quarantine) with explicit treatment of EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain` as the basis for M002 cleanup.
patterns_established:
  - Treat milestone-level classification notes as shared contracts for later slices, referenced directly from requirements rather than re-encoding logic in each slice.
observability_surfaces:
  - none (documentation-only task; later slices observe behavior via classification inventories and cleanup diffs).
duration: ~45m
verification_result: passed
completed_at: 2026-03-13
blocker_discovered: false
---

# T02: Define classification rules and agent status treatment

**Defined workflow-engine-centric classification rules for keep/freeze/deprecate/remove/quarantine, and wired them into requirements as the input for M002 cleanup decisions.**

## What Happened

- Read `.gsd/milestones/M002/M002-TRUTH-NOTE.md`, `.gsd/REQUIREMENTS.md`, and the S01 plan to anchor classification in the M001 kernel, representative weekly scheduling workflow, and existing R001–R005 definitions.
- Created `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` with:
  - Status definitions for **keep**, **freeze**, **deprecate**, **remove**, and **quarantine** framed explicitly in terms of the workflow-engine truth set and M002 cleanup goals.
  - Criteria and behavioral rules for each status (when to use it, what future work can/cannot do with artifacts in that status).
  - Concrete examples for each status drawn from existing Helm surfaces and packages (kernel tables and orchestration modules for keep; StudyAgent and historical docs for freeze; legacy helpers and protocol versions for deprecate; unused experimental scripts and fixtures for remove; historical workflows and rich runbooks for quarantine).
  - An "Agent and Integration Treatment" section that binds specific actors to statuses:
    - TaskAgent and CalendarAgent → **keep** as the only truth-defining agents.
    - EmailAgent → **deprecate**, with an expectation that S02 will either remove or quarantine email flows and planning artifacts.
    - StudyAgent → **freeze**, matching the truth note's frozen status and forbidding new kernel dependencies.
    - LinkedIn integrations → **deprecate**, with a bias toward removal or quarantine in S02.
    - Night Runner / cron-like experimental flows → **deprecate**, to be removed or quarantined while ensuring core workflows remain intact.
    - `packages/domain` → default **quarantine**, with room for S02 to selectively keep or remove specific pieces that are actually used.
  - Guidance on how S02 should apply these rules during cleanup (bias toward remove for unused non-truth artifacts, use freeze/quarantine sparingly with rationale) and how S03 should verify that post-cleanup behavior still aligns with the truth note.
- Updated `.gsd/REQUIREMENTS.md` to connect cleanup requirements to the new rules:
  - For **R002** (repo working set reduced): extended the Notes to reference `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` as the source of status definitions and the primary input to S02 decisions about what to keep/freeze/deprecate/remove/quarantine.
  - For **R005** (deprecated paths clearly marked/removed): extended the Notes to reference the same rules file as the description of how deprecated paths (including LinkedIn, Night Runner, and `packages/domain`) are tagged and how S02 will choose between removal and quarantine.
  - Left validation status for R002/R005 unchanged (still unmapped) while clarifying the path to proof via S02.

## Verification

- Confirmed `cat .gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` shows:
  - Clear definitions, criteria, behavioral rules, and examples for keep/freeze/deprecate/remove/quarantine.
  - Explicit treatment of TaskAgent/CalendarAgent, EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain` that is consistent with the M002 truth note.
  - Concrete guidance for S02/S03 on how to apply these rules.
- Confirmed `cat .gsd/REQUIREMENTS.md` shows:
  - R002 Notes referencing `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` as the definition of statuses and the main input for S02 cleanup.
  - R005 Notes referencing the same rules for deprecated paths (LinkedIn, Night Runner, `packages/domain`) and explaining how those tags will drive S02 decisions.
  - Validation fields for R002/R005 left as `unmapped`, with the new notes making the future proof surface explicit.

## Diagnostics

- Classification rules: `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` is the single contract for status semantics (keep/freeze/deprecate/remove/quarantine) and for how agents/integrations are treated in M002.
- Requirements mapping: `.gsd/REQUIREMENTS.md` (R002/R005 sections and traceability notes) show how these rules will be used as inputs and eventual proof surfaces for cleanup slices.
- If later slices are unsure how to classify an artifact, they should first consult the truth note, then this rules file, and only then extend or amend the rules with explicit rationale.

## Deviations

- None. The task followed the written plan: defined workflow-engine-centric classification rules, bound the treatment of EmailAgent/StudyAgent/LinkedIn/Night Runner/`packages/domain` to explicit statuses, and updated R002/R005 notes to reference the rules as inputs for S02.

## Known Issues

- No slice-level inventory was created here; S01/T03 is still responsible for applying these rules across major components in `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`.

## Files Created/Modified

- `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` — New classification rules note defining keep/freeze/deprecate/remove/quarantine in terms of the workflow-engine truth set, with explicit agent/integration treatment and examples.
- `.gsd/REQUIREMENTS.md` — Updated R002 and R005 Notes to reference the classification rules doc as the input and eventual proof surface for cleanup decisions.
- `.gsd/milestones/M002/slices/S01/S01-PLAN.md` — Marked T02 as completed in the slice plan.
