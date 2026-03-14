---
id: S01
parent: M002
milestone: M002
provides:
  - Workflow-engine truth note, classification rules, and initial inventory for Helm's current truth set
requires:
  - slice: none
    provides: n/a
affects:
  - S02
key_files:
  - .gsd/milestones/M002/M002-TRUTH-NOTE.md
  - .gsd/milestones/M002/M002-CLASSIFICATION-RULES.md
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
  - .gsd/REQUIREMENTS.md
  - .gsd/PROJECT.md
key_decisions:
  - Treat the M001 kernel and representative weekly scheduling workflow as the sole behavioral truth for Helm in M002; all other agents and integrations are non-truth unless explicitly reclassified.
  - Use milestone-level truth and classification notes as the primary contracts for cleanup and future planning, referenced directly from requirements.
  - Treat EmailAgent as deprecated and StudyAgent as frozen for this version; TaskAgent and CalendarAgent remain the only truth-defining agents.
patterns_established:
  - Use concise milestone truth notes and classification docs as shared contracts, with `.gsd/REQUIREMENTS.md` tracing directly to them.
  - Maintain a single milestone-level classification inventory as the entry point for cleanup work, refined by later slices rather than rediscovered.
observability_surfaces:
  - none (documentation-only slice; later slices observe behavior via tests, cleanup diffs, and UAT scripts).
drill_down_paths:
  - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T03-SUMMARY.md
duration: ~3h
verification_result: passed
completed_at: 2026-03-13
---

# S01: Define Helm workflow-engine truth set

**Defined a workflow-engine-centric truth note, classification rules, and an initial inventory that together fix Helm's current truth set and prepare the tree for cleanup.**

## What Happened

S01 compressed the M001 kernel outputs and existing project docs into an explicit truth set and a cleanup contract:

- Wrote `.gsd/milestones/M002/M002-TRUTH-NOTE.md` centered on the M001 kernel and representative weekly scheduling workflow, defining the workflow-engine truth set, operator surfaces in scope (API and Telegram), and a clear core vs non-core split for agents. TaskAgent and CalendarAgent are the only truth-defining agents; EmailAgent and StudyAgent are non-core, with StudyAgent frozen and email planning artifacts de-scoped as canonical truth.
- Updated `.gsd/REQUIREMENTS.md` to treat the truth note as the primary proof surface for R001 (truth set sharply defined) and R004 (non-core agents do not define truth), marking both as proofed and wiring notes and traceability directly to the truth note.
- Authored `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`, defining keep/freeze/deprecate/remove/quarantine in terms of the workflow-engine truth set, with criteria, behavioral rules, and concrete examples. The rules include explicit treatment for EmailAgent (deprecate), StudyAgent (freeze), LinkedIn (deprecate), Night Runner (deprecate), and `packages/domain` (quarantine-by-default).
- Extended `.gsd/REQUIREMENTS.md` entries for R002 and R005 so their notes reference the classification rules as the input contract for cleanup and deprecated-path handling, while leaving their validation status unmapped pending S02.
- Scanned major packages, apps, docs, and tests and recorded `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`, tagging components by status (keep/freeze/deprecate/remove/quarantine) in line with the truth note and rules. Kernel, storage, orchestration, LLM, connectors, and operator apps are keep; EmailAgent is deprecate; StudyAgent and its app/docs are freeze; LinkedIn and Night Runner paths are deprecate; `packages/domain` and related domain docs are quarantine; tests and fixtures are keep with S02 expected to refine unused pieces.
- Updated `.gsd/PROJECT.md` to reference the classification inventory as the working set for M002 cleanup and to document that the repo currently contains non-truth agents/integrations that will be cleaned up under M002.
- Left `.gsd/DECISIONS.md` unchanged for now; existing decisions already capture the kernel patterns and operator-surface alignment that this slice depended on.

## Verification

Slice-level verification reused the task checks:

- Confirmed `cat .gsd/milestones/M002/M002-TRUTH-NOTE.md` shows a concise workflow-engine-centric truth definition aligned with M001, including core vs non-core agent treatment and explicit non-truth boundaries (email, LinkedIn, Night Runner, `packages/domain`, historical specs/tests).
- Confirmed `cat .gsd/REQUIREMENTS.md` shows R001 and R004 with Validation: proofed and notes pointing to the truth note, and R002/R005 notes referencing the classification rules as cleanup inputs.
- Confirmed `cat .gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` defines keep/freeze/deprecate/remove/quarantine with criteria, examples, and explicit treatment for EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain`.
- Confirmed `cat .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` tags major packages/apps/docs/tests (including EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain`) with statuses and rationales that reference the truth note and rules.
- Confirmed `.gsd/PROJECT.md` references the classification inventory under the M002 milestone as the working cleanup set.

## Requirements Advanced

- R001 — Advanced from implicit kernel understanding to an explicit truth note wired into `.gsd/REQUIREMENTS.md` as the proof surface for the workflow-engine truth set.
- R004 — Advanced by formally encoding non-core agent treatment (EmailAgent deprecated, StudyAgent frozen) in the truth note, and by reflecting that constraint in requirements notes and classification rules.
- R002 — Advanced indirectly: S01 produced the classification rules and initial inventory that S02 will use to reduce the working set to active and frozen truth.
- R005 — Advanced indirectly: S01 documented how deprecated paths (LinkedIn, Night Runner, `packages/domain`) are tagged and surfaced for S02 removal/quarantine.

## Requirements Validated

- R001 — Validated as proofed via `.gsd/milestones/M002/M002-TRUTH-NOTE.md` and its wiring into `.gsd/REQUIREMENTS.md`.
- R004 — Validated as proofed via the truth note's explicit core vs non-core agent treatment and the corresponding notes in `.gsd/REQUIREMENTS.md`.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- None. The slice followed the S01 plan: authored the truth note, classification rules, and initial classification inventory, and wired them into requirements and the project description.

## Known Limitations

- The classification inventory is intentionally coarse-grained (package/app/doc/test-suite level). S02 must refine statuses at module/file level, especially within `packages/connectors`, `packages/domain`, tests, and fixtures.
- Some deprecate/quarantine decisions (EmailAgent removal vs quarantine, LinkedIn/Night Runner reachability, precise `packages/domain` split) remain to be validated against actual usage in the representative workflow during S02.
- No runtime behavior was exercised in this slice; verification is purely documentation/contracts. S03 will provide live verification that task/calendar workflows still operate after cleanup.

## Follow-ups

- S02: Apply the classification rules and inventory to the tree, refining statuses per module/file, removing or quarantining deprecated artifacts, and updating tests/CI to match the truth set.
- S03: Design and implement UAT plus test coverage that treats task/calendar workflows as the protected core and confirms behavior after cleanup.

## Files Created/Modified

- `.gsd/milestones/M002/M002-TRUTH-NOTE.md` — Truth note defining the workflow-engine-centric Helm truth set for M002.
- `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` — Classification rules for keep/freeze/deprecate/remove/quarantine grounded in the truth set.
- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — Initial classification inventory tagging major packages/apps/docs/tests by status.
- `.gsd/REQUIREMENTS.md` — Updated to reference the truth note and classification rules and to mark R001/R004 as proofed.
- `.gsd/PROJECT.md` — Updated to reference the M002 classification inventory as the working cleanup set.
- `.gsd/milestones/M002/slices/S01/S01-PLAN.md` — Tasks T01–T03 marked as completed.
- `.gsd/STATE.md` — Updated phase/next action to reflect S01 documentation work (by prior tasks and this slice).

## Forward Intelligence

### What the next slice should know

- The truth note and classification rules are the contracts; avoid restating semantics in S02/S03. When a component's status is unclear, read the truth note first, then the classification rules, then update the inventory with rationale.
- The representative weekly scheduling workflow is the only behavior that defines truth. When deciding whether to remove or quarantine a path, always ask whether that path is required for this workflow through API/worker/Telegram.
- EmailAgent and StudyAgent are present but not truth-defining. S02 should be comfortable treating email flows as deprecate→remove/quarantine and must not add new dependencies on StudyAgent.

### What's fragile

- The coarse inventory around `packages/domain` and some connectors is thin; it assumes these layers are mostly aspirational. If S02 discovers real dependencies into these areas, the inventory and rules need to be updated rather than worked around.
- Deprecated paths like LinkedIn and Night Runner may still be partially wired; S02 needs to verify reachability before removal to avoid surprising test or runtime failures.

### Authoritative diagnostics

- Truth semantics: `.gsd/milestones/M002/M002-TRUTH-NOTE.md` — authoritative definition of what Helm is for M002.
- Classification semantics: `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` — authoritative definition of keep/freeze/deprecate/remove/quarantine and agent/integration treatment.
- Cleanup target map: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — authoritative starting point for S02 cleanup.

### What assumptions changed

- Assumption: Historical multi-agent planning docs and integrations implicitly defined current truth.
  - Reality: Truth is now explicitly constrained to the M001 kernel and weekly scheduling workflow; historical artifacts are non-truth unless reclassified.
- Assumption: EmailAgent and StudyAgent were first-class peers to TaskAgent/CalendarAgent.
  - Reality: TaskAgent and CalendarAgent are the only truth-defining agents; EmailAgent is deprecated and StudyAgent is frozen for this version.
