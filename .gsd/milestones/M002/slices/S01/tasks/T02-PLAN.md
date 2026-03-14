# T02: Define classification rules and agent status treatment

## Goal
Define concrete classification rules (keep/freeze/deprecate/remove/quarantine) grounded in the M002 workflow-engine truth note, and make the treatment of core vs non-core agents explicit for later cleanup slices.

## Must-Haves
- A small, explicit classification rules doc that defines each status in terms of the M002 truth set.
- At least one real example for each status drawn from existing Helm artifacts.
- Explicit treatment of EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain` that is consistent with the truth note.
- `.gsd/REQUIREMENTS.md` updated so R002/R005 notes/proof hints reference the classification rules as inputs for S02.

## Plan
1. Re-read `.gsd/milestones/M002/M002-TRUTH-NOTE.md` and `.gsd/REQUIREMENTS.md` (R001–R005) to anchor the rules in the established truth set.
2. Draft `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`:
   - Define keep/freeze/deprecate/remove/quarantine in terms of the workflow-engine truth set and M002 goals.
   - For each status, include at least one concrete example artifact (code, doc, test, or integration).
   - Describe how non-core agents and deprecated paths should be treated across slices (e.g., frozen, removed, quarantined).
3. Make agent status treatment explicit:
   - Encode the core/non-core split from the truth note.
   - Spell out expected classification for EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain`.
4. Update `.gsd/REQUIREMENTS.md`:
   - For R002 and R005, add notes/proof hints that reference the classification rules doc as an input for S02.
   - Leave validation status as-is (unmapped) but ensure the path to proof is clear.
5. Run slice-level verification checks relevant to this task:
   - Confirm `cat .gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` shows clear rules and examples for all statuses.
   - Confirm `.gsd/REQUIREMENTS.md` mentions the classification rules under R002/R005 notes or proof hints.

## Observability / Diagnostics
- Inspection surfaces: `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` and updated `.gsd/REQUIREMENTS.md`.
- Failure visibility: If later slices cannot decide how to classify an artifact, gaps or ambiguity in the rules/examples here should be the first place to look.
