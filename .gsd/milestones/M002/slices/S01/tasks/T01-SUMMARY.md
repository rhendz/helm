---
id: T01
parent: S01
milestone: M002
provides:
  - Workflow-engine truth note aligned with M001 kernel and representative weekly scheduling workflow, plus updated requirement traces for R001/R004.
key_files:
  - .gsd/milestones/M002/M002-TRUTH-NOTE.md
  - .gsd/REQUIREMENTS.md
key_decisions:
  - Treat the M001 kernel and representative weekly scheduling workflow as the sole behavioral truth for Helm in M002; all additional agents and historical integrations are non-truth unless explicitly reclassified.
patterns_established:
  - Use concise milestone truth notes as the primary proof surface for requirements and classification rules, with `.gsd/REQUIREMENTS.md` tracing directly to them.
observability_surfaces:
  - none (documentation-only task; future slices will observe behavior via classification docs and requirements traces).
duration: ~1h
verification_result: passed
completed_at: 2026-03-13
blocker_discovered: false
---

# T01: Write workflow-engine truth note and map to requirements

**Defined the M002 workflow-engine truth note around the M001 kernel and weekly scheduling workflow, and wired R001/R004 in `.gsd/REQUIREMENTS.md` to treat it as the primary proof surface.**

## What Happened

- Read `.gsd/milestones/M001/M001-SUMMARY.md`, `.gsd/DECISIONS.md`, `.gsd/PROJECT.md`, and `.gsd/REQUIREMENTS.md` to ground the truth note in the validated kernel and existing requirement definitions.
- Created `.gsd/milestones/M002/M002-TRUTH-NOTE.md` with:
  - A kernel-centric definition of the Helm truth set, anchored to durable workflow tables, orchestration services, specialist dispatch, approval checkpoints, sync/recovery semantics, and shared operator surfaces.
  - An explicit statement that the representative weekly scheduling workflow is the only workflow that currently defines end-to-end behavior, and that any new workflow is non-truth until it reuses the kernel contracts and is equivalently verified.
  - Boundaries on operator surfaces, limiting truth to the existing API and Telegram workflows/replay paths and excluding any additional dashboards or experimental UIs.
  - An explicit core/non-core split for agents: TaskAgent and CalendarAgent as truth-defining; EmailAgent and StudyAgent as non-core, with StudyAgent frozen and email planning artifacts de-scoped as canonical truth.
  - A list of categories that do not define truth (legacy email flows, LinkedIn, Night Runner, `packages/domain`, and historical specs/tests), to be handled by later classification and cleanup slices.
  - A short section on how this note will be used by M002 classification rules, inventory, and requirements R001/R004.
- Updated `.gsd/REQUIREMENTS.md` to map requirements to this truth note:
  - For **R001**, set `Validation: proofed` and updated the notes to reference `.gsd/milestones/M002/M002-TRUTH-NOTE.md` as the written truth set and the anchor for classification rules and inventory.
  - For **R004**, set `Validation: proofed` and updated the notes to reference the truth note’s explicit treatment of TaskAgent/CalendarAgent as core and EmailAgent/StudyAgent as non-core/frozen, and to call out that classification rules/inventory will enforce this constraint.
  - Updated the traceability table to mark R001 and R004 as `proofed` instead of `unmapped`, pointing at the truth note as their proof surface while leaving R002/R003/R005 unmapped for later slices.

## Verification

- Confirmed that `cat .gsd/milestones/M002/M002-TRUTH-NOTE.md` shows a concise workflow-engine-centric truth definition aligned with M001 decisions and the representative weekly scheduling workflow, including explicit core vs non-core agent treatment and non-truth boundaries.
- Confirmed that `cat .gsd/REQUIREMENTS.md` shows:
  - R001 and R004 with `Validation: proofed`.
  - Notes for R001 and R004 that explicitly reference `.gsd/milestones/M002/M002-TRUTH-NOTE.md` and describe how it encodes the truth set and non-core agent constraints.
  - The traceability table rows for R001 and R004 updated to `proofed`, leaving other active requirements unchanged.

## Diagnostics

- Truth definition: `.gsd/milestones/M002/M002-TRUTH-NOTE.md` is the single source of truth for the M002 workflow-engine truth set and core vs non-core agents.
- Requirements mapping: `.gsd/REQUIREMENTS.md` (R001/R004 sections and the traceability table) shows how the truth note is used as a proof surface.
- Later slices (classification rules and inventory) should link back to this file rather than restating the truth set.

## Deviations

- None. The task followed the written plan: drafted a concise kernel- and workflow-centered truth note, explicitly called out Task/Calendar as core and Email/Study as non-core/frozen, and wired R001/R004 to this note as their proof surface.

## Known Issues

- None specific to this task. Subsequent S01 tasks still need to define concrete classification rules and an initial inventory that consume this truth note.

## Files Created/Modified

- `.gsd/milestones/M002/M002-TRUTH-NOTE.md` — New truth note defining the workflow-engine-centric Helm truth set for M002, centered on the M001 kernel and representative weekly scheduling workflow, with explicit core vs non-core agent treatment and non-truth boundaries.
- `.gsd/REQUIREMENTS.md` — Updated R001/R004 validation status, notes, and traceability table entries to reference the M002 truth note as their primary proof surface.
