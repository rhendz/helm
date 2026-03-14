---
estimated_steps: 6
estimated_files: 10
---

# T01: Map and confirm deprecated/quarantine targets against live usage

**Slice:** S02 — Repo cleanup and deprecation enforcement
**Milestone:** M002

## Description

Inventory and confirm all live usages of deprecated or aspirational paths (LinkedIn, Night Runner, `helm_domain`/`packages/domain`, and Email/Study surfaces) across code, docs, tests, and CI. Refine the M002 classification inventory to file/module granularity so later tasks can safely remove or quarantine artifacts without breaking the workflow-engine truth set or task/calendar workflows.

## Steps

1. Skim `.gsd/milestones/M002/M002-TRUTH-NOTE.md` and `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` to refresh truth-set and classification semantics for Email/Study, LinkedIn, Night Runner, and `packages/domain`.
2. Use `rg` across the repo to locate all references to `linkedin`, `Night Runner`/`night-runner`, and `helm_domain`, plus key Email/Study symbols (e.g., `EmailAgent`, `StudyAgent`, `email_message_ingest`). Capture results grouped by package/app/docs/tests.
3. For each category (LinkedIn, Night Runner, `packages/domain`, Email/Study docs/specs/tests), inspect the matched files to determine whether they participate in the representative weekly scheduling / task+calendar workflow or are isolated/deprecated surfaces.
4. Update `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` to add per-file or per-module entries for LinkedIn, Night Runner, `packages/domain`, and Email/Study docs/specs/tests, tagging each as keep/freeze/deprecate/remove/quarantine with short rationale.
5. Identify any surprising or risky couplings (for example, domain models used by core storage, LinkedIn symbols referenced from generic connector wiring, or Email/Study tests touching core storage contracts) and note them explicitly in the inventory for T02/T03 to respect.
6. Re-run the `rg` commands to confirm that all matched files are now represented in the inventory with clear statuses and that there are no large, unexplained pockets of deprecated usage.

## Must-Haves

- [ ] All LinkedIn, Night Runner, `packages/domain`, and Email/Study-related files referenced by `rg` have explicit entries in the classification inventory with keep/freeze/deprecate/remove/quarantine tags.
- [ ] Any surprising couplings between deprecated layers and the workflow-engine core are called out in the inventory with guidance for later tasks.

## Verification

- `rg "linkedin" .` and `rg "night runner|night-runner" .` show only files that are explicitly listed in `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` with appropriate statuses.
- `rg "helm_domain" .` and targeted searches for `EmailAgent`, `StudyAgent`, and `email_message_ingest` have all matched files represented in the updated inventory.

## Inputs

- `.gsd/milestones/M002/M002-TRUTH-NOTE.md` — defines the workflow-engine truth set and agent status (core vs non-core).
- `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` — describes semantics for keep/freeze/deprecate/remove/quarantine and the treatment of LinkedIn, Night Runner, `packages/domain`, EmailAgent, and StudyAgent.
- Existing `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — coarse-grained package/app/doc/test statuses to refine.

## Expected Output

- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — updated with per-file/module entries for LinkedIn, Night Runner, `packages/domain`, and Email/Study docs/specs/tests, including notes on any risky couplings to respect in later cleanup tasks.

## Observability Impact

This task does not add new runtime behavior or logging, but it changes how future agents and humans inspect deprecated surfaces:
- **Classification inventory**: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` becomes the primary diagnostic surface for what is safe to remove vs must be quarantined for LinkedIn, Night Runner, `packages/domain`, and Email/Study artifacts.
- **rg scans as checks**: `rg "linkedin" .`, `rg "night runner|night-runner" .`, `rg "helm_domain" .`, and targeted searches for `EmailAgent`, `StudyAgent`, and `email_message_ingest` are the diagnostic commands to validate that all deprecated usages are tracked and classified.
- **Failure modes**: If later slices remove or quarantine artifacts and tests/imports fail, the gap should show up as either:
  - a missing entry in the classification inventory for a file that still references deprecated paths, or
  - a stale classification entry that no longer matches the repo tree.
Future cleanup tasks should treat discrepancies between `rg` output and the inventory as the primary failure state to resolve.
