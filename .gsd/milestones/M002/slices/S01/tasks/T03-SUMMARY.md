---
id: T03
parent: S01
milestone: M002
provides:
  - Initial classification inventory of major Helm components tagged by keep/freeze/deprecate/remove/quarantine, wired into the project description as the M002 cleanup working set.
key_files:
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
  - .gsd/PROJECT.md
key_decisions:
  - Treat the M002 classification inventory as the authoritative starting point for S02 cleanup, tagging major components by status at package/app/doc/test granularity rather than per-file.
patterns_established:
  - Use a single milestone-level inventory doc as the entry point for cleanup work, with S02/S03 refining statuses within its coarse-grained categories instead of rediscovering the tree.
observability_surfaces:
  - none (documentation-only task; later slices observe behavior via code/tree diffs and requirement proof surfaces).
duration: ~1h
verification_result: passed
completed_at: 2026-03-13
# Set blocker_discovered: true only if execution revealed the remaining slice plan
# is fundamentally invalid (wrong API, missing capability, architectural mismatch).
# Do NOT set true for ordinary bugs, minor deviations, or fixable issues.
blocker_discovered: false
---

# T03: Build initial classification inventory for major components

**Created a first-pass classification inventory for major Helm components and wired it into the project description as the M002 cleanup working set.**

## What Happened

- Read the S01 plan, M002 truth note, and classification rules to anchor the inventory in the workflow-engine truth set and status semantics.
- Scanned the repo layout (packages/apps/docs/tests) to identify major component boundaries: kernel/storage/orchestration, agents/connectors, operator apps, LLM/runtime/observability support, domain layer, docs/specs, and tests/fixtures.
- Created `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` with:
  - A short purpose section plus a summary-by-status block that restates how keep/freeze/deprecate/remove/quarantine apply at a high level.
  - An inventory section that tags major components by status:
    - **Kernel and orchestration** (`packages/storage`, `packages/orchestration`, `packages/runtime`, `packages/observability`) as **keep**.
    - **Agents and connectors**:
      - TaskAgent and CalendarAgent modules as **keep**.
      - EmailAgent module as **deprecate** (to be removed or quarantined in S02).
      - StudyAgent module as **freeze**.
      - `packages/connectors` as **keep** at the package level, with a LinkedIn connector path explicitly called out as **deprecate**.
    - **Domain layer**: `packages/domain` as **quarantine`**, matching the truth note and classification rules.
    - **LLM/prompting**: `packages/llm` as **keep** for core workflow prompting, with room for S02 to trim unused pieces.
    - **Operator surfaces**: `apps/api`, `apps/worker`, and `apps/telegram-bot` as **keep`; `apps/study-agent` as **freeze`; a Night Runner app (if present) as **deprecate**.
    - **Docs/specs**: runbooks and the internal Helm spec (`docs/runbooks`, `docs/internal/helm-v1.md`) as **keep**; planning docs as **freeze**; domain docs as **quarantine**.
    - **Tests**: orchestration, connectors, and LLM unit tests as **keep**; integration tests as **keep** with S02 expected to deprecate non-truth flows; fixtures as **keep** with remove candidates for unused ones.
    - **Miscellaneous**: StudyAgent v2/v3 design docs as **freeze**; Night Runner / legacy cron scripts under `scripts/` as **deprecate`**.
  - A notes-for-S02 section that explains this is a broad-but-shallow pass, and asks S02 to prefer `remove` for clearly unused non-truth artifacts while treating `freeze` and `quarantine` as deliberate exceptions.
- Updated `.gsd/PROJECT.md` under the M002 milestone bullet to reference `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` as the working inventory for M002 cleanup.
- Left `.gsd/DECISIONS.md` unchanged; no new architectural or pattern decisions beyond applying existing truth/rule contracts to concrete components.

## Verification

- Confirmed `cat .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` shows:
  - A purpose section, status summary, and an inventory that tags major packages/apps/docs/tests including EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain`.
  - Rationales that explicitly reference the M002 truth note and classification rules.
- Confirmed `cat .gsd/PROJECT.md` shows the M002 milestone bullet with a sub-point referencing `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` as the working inventory for cleanup.
- Confirmed `.gsd/milestones/M002/slices/S01/S01-PLAN.md` has T03 marked as completed and `.gsd/STATE.md` no longer points at T03 as the next action.

## Diagnostics

- Classification inventory: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` is the entry point for S02; it lists major components with statuses and rationales.
- Project wiring: `.gsd/PROJECT.md` (M002 section) points to the inventory as the working cleanup set.
- Upstream contracts: `.gsd/milestones/M002/M002-TRUTH-NOTE.md` and `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` define the truth set and status semantics that this inventory applies.

## Deviations

- None. The task followed the written plan: produced a broad first-pass inventory tagging major components (including EmailAgent, StudyAgent, LinkedIn, Night Runner, and `packages/domain`) and wired it into `.gsd/PROJECT.md` as the M002 cleanup working set.

## Known Issues

- Inventory is intentionally coarse-grained; S02 still needs to:
  - Refine statuses at module/file level (especially within `packages/connectors`, `packages/domain`, and tests/fixtures).
  - Confirm whether any LinkedIn/Night Runner code paths are still reachable and adjust deprecate vs remove vs quarantine accordingly.
  - Reconcile inventory entries with actual usage in the representative weekly scheduling workflow; if conflicts appear, the truth note and rules should drive updates to the inventory.

## Files Created/Modified

- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — New initial classification inventory tagging major packages/apps/docs/tests by keep/freeze/deprecate/remove/quarantine in line with the M002 truth note and classification rules.
- `.gsd/milestones/M002/slices/S01/S01-PLAN.md` — Marked T03 as completed in the slice plan.
- `.gsd/PROJECT.md` — Updated M002 milestone description to reference the classification inventory as the working set for cleanup.
- `.gsd/STATE.md` — Updated next action to reflect T03 completion and await subsequent slice work.
