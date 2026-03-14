---
id: T01
parent: S02
milestone: M002
provides:
  - Refined per-file/module classification inventory for deprecated and quarantined surfaces
key_files:
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
key_decisions:
  - EmailAgent runtime/storage/worker wiring remains present but is explicitly classified as deprecated and non-truth, with storage contracts kept for now.
  - `packages/domain` is treated as a quarantined aspirational layer; its models are unused and safe to quarantine, with only PYTHONPATH references remaining.
  - Night runner scripts and runbooks are classified as deprecated/quarantined experimental cron flows, explicitly outside the workflow-engine truth set.
patterns_established:
  - Use rg-based sweeps plus a maintained classification inventory as the diagnostic surface for deprecated integrations.
observability_surfaces:
  - rg "night runner|night-runner" .
  - rg "helm_domain" .
  - rg "EmailAgent" .
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
duration: ~60m
verification_result: passed
completed_at: 2026-03-13T21:56:00-07:00
blocker_discovered: false
---

# T01: Map and confirm deprecated/quarantine targets against live usage

**Refined the M002 classification inventory to per-file/module granularity for Night Runner, `packages/domain`, and EmailAgent-related runtime/docs/tests, with explicit notes on risky couplings.**

## What Happened

- Read the M002 truth note, classification rules, and initial inventory to align on status semantics and the workflow-engine truth set.
- Fixed an observability gap in the T01 task plan by adding an `## Observability Impact` section that documents rg-based diagnostics and the role of the classification inventory as the inspection surface for deprecated paths.
- Used ripgrep sweeps to locate all current references to:
  - Night Runner / night-runner scripts and runbooks.
  - `helm_domain` / `packages/domain`.
  - EmailAgent-related runtime, storage, worker jobs, and docs.
- Verified the current tree does not contain any concrete LinkedIn connector code; LinkedIn exists only as a planned integration in the classification rules.
- Inspected code and scripts for each matched category to determine how they relate to the representative weekly scheduling / task+calendar workflow vs non-truth experimental flows:
  - Night Runner: confined to scripts and docs; not wired into kernel, apps, or tests.
  - `packages/domain`: provides an unused `ActionItem` dataclass and has no imports from or into core code; referenced only via PYTHONPATH additions in helper scripts.
  - EmailAgent: has a full runtime surface (agents package, runtime protocol, Helm runtime wrapper, storage models/repositories, worker jobs, and unit tests) but is clearly separate from the kernel-defined task/calendar workflows.
- Rewrote `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` into a refined S02/T01 pass that:
  - Preserves the prior high-level component statuses.
  - Adds per-file/module entries for:
    - Night Runner scripts (`scripts/night-runner.sh`, `scripts/install-night-runner-cron.sh`) and runbooks (`docs/runbooks/night-runner*.md`) with deprecate/quarantine tags.
    - `packages/domain` and its `helm_domain` models, plus the scripts that add `packages/domain/src` to PYTHONPATH.
    - EmailAgent runtime modules, Helm runtime wrapper, storage models and repositories, worker jobs, and associated docs/tests, with explicit keep/deprecate/quarantine decisions.
  - Captures surprising couplings between deprecated layers (especially EmailAgent) and core storage/runtime/worker components so T02/T03 can respect them during removal/quarantine.

## Verification

- Ran rg sweeps before and after updating the inventory to confirm coverage:
  - `rg "night runner|night-runner" .` — all matches are in `docs/runbooks/night-runner*.md`, `scripts/night-runner.sh`, `scripts/install-night-runner-cron.sh`, and `docs/internal/helm-v1.md`; each of these files now has an explicit inventory entry and status.
  - `rg "helm_domain" .` — matches are limited to the domain package and PYTHONPATH settings in helper scripts; all covered in the inventory with quarantine/deprecate tags.
  - `rg "EmailAgent" .`, `rg "email_message_ingest" .` — matches in EmailAgent runtime files, Helm runtime, storage repositories, worker jobs, and unit tests; all referenced explicitly in the refined inventory.
- Confirmed that LinkedIn is only mentioned in the classification rules and inventory (logical deprecate/remove) and does not appear in `packages/`, `apps/`, `tests/`, or `docs/` code paths.
- Verified that for each rg match in the Night Runner, `packages/domain`, and EmailAgent categories, there is now a corresponding entry in `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` with a clear status and short rationale.

## Diagnostics

To inspect and validate the mapping in future tasks:

- Use ripgrep sweeps as primary diagnostics for deprecated/quarantined surfaces:
  - `rg "night runner|night-runner" .`
  - `rg "helm_domain" .`
  - `rg "EmailAgent" .`
  - `rg "email_message_ingest" .`
- Compare rg output to the refined inventory:
  - `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` should contain an entry for every matched file in these categories.
  - Any new match without an inventory entry indicates a missed or newly introduced coupling that T02/T03 must classify before removal/quarantine.
- Treat discrepancies between rg results and the inventory (missing entries or stale paths) as the primary failure mode when cleanup tasks remove or quarantine code.

## Deviations

- None. The work followed the task plan: mapped usages via rg, inspected matched files for workflow relevance, and refined the classification inventory to file/module granularity with explicit statuses and coupling notes.

## Known Issues

- LinkedIn remains a logical deprecate/remove entry in the inventory without concrete code in the tree; if a LinkedIn connector is introduced in the future, it must be explicitly classified and evaluated against the truth set.
- EmailAgent flows are still fully wired (runtime, storage, worker jobs, and tests). T02/T03 will need to decide how much of this surface to remove vs quarantine while keeping storage contracts and tests healthy.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S02/tasks/T01-PLAN.md` — Added an `## Observability Impact` section describing rg scans and the classification inventory as the inspection surface for deprecated paths.
- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — Rewrote as a refined S02/T01 pass with per-file/module entries and explicit statuses/rationales for Night Runner, `packages/domain`, EmailAgent runtime/storage/docs/tests, and logical LinkedIn artifacts.
- `.gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md` — New task summary capturing the refined inventory and verification.
