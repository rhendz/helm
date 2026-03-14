# Requirements

## Validated

- **REQ-DURABLE-PERSISTENCE**: Durable workflow runs, steps, artifacts, and lineage are persisted and inspectable — validated in M001 (S01 established core tables with typed repositories and hermetic test coverage).
- **REQ-SPECIALIST-DISPATCH**: Typed TaskAgent and CalendarAgent dispatch with durable invocation records — validated in M001 (specialist invocation table with input/output artifact linkage).
- **REQ-APPROVAL-CHECKPOINTS**: Approval checkpoints, revision-driven proposal versioning, and kernel-owned resume semantics — validated in M001.
- **REQ-ADAPTER-SYNC**: Adapter-gated sync execution with idempotency, retry, replay, and recovery classification — validated in M001.
- **REQ-REPRESENTATIVE-WORKFLOW**: Representative weekly scheduling workflow from request through approved writes and replay-aware final lineage — validated in M001.
- **REQ-OPERATOR-SURFACES**: Telegram and API operator tooling for workflow status, approval, replay, and lineage inspection — validated in M001.
- **R002** — Repo working set is reduced to active and frozen truth
  - Class: continuity
  - Status: validated
  - Description: S02 physically quarantined aspirational domain code, constrained Night Runner to deprecated scripts plus archived docs, confirmed LinkedIn has no live implementation, and kept tests/CI green without relying on these paths.
  - Why it matters: Reduces cognitive load and prevents future work from building on dead paths just because files remain in the tree.
  - Source: user
  - Primary owning slice: M002/S02
  - Supporting slices: M002/S01, M002/S03
  - Validation: validated
  - Notes: Classification inventory and rg-based diagnostics provide the ongoing guardrail.
- **R005** — Deprecated paths are clearly marked and removed where safe
  - Class: failure-visibility
  - Status: validated
  - Description: LinkedIn, Night Runner, and packages/domain are explicitly classified as deprecated/quarantined, removed from live import paths, and discoverable via diagnostics.
  - Why it matters: Prevents future milestones from seeing these paths as live options and reduces risk of accidentally reviving deprecated architecture.
  - Source: user
  - Primary owning slice: M002/S02
  - Supporting slices: M002/S01
  - Validation: validated
  - Notes: docs/archive/, the classification inventory, and rg sweeps are the authoritative signals for deprecated surfaces.

## Active

### R001 — Helm workflow-engine truth set is sharply defined
- Class: core-capability
- Status: active
- Description: The current-version Helm truth set is explicitly defined around the workflow engine, replay/recovery/approvals, task/calendar sync protection, and the Telegram/API/worker surfaces that support those flows.
- Why it matters: Future milestones must not rely on stale, implicit, or aspirational artifacts to infer what Helm is; planning should start from a small, explicit truth set.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: none yet
- Validation: proofed
- Notes: Truth set is defined in `.gsd/milestones/M002/M002-TRUTH-NOTE.md` (M002/S01) and used as the anchor for classification rules and inventory.

### R003 — Task/calendar workflows remain intact and verified after cleanup
- Class: continuity
- Status: validated
- Description: After truth-set cleanup and artifact removal, the representative weekly scheduling / task+calendar workflows continue to operate correctly through API/worker/Telegram, with explicit verification/UAT demonstrating no regressions.
- Why it matters: Task/calendar sync protection is core truth; cleanup must not break existing behavior.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S01, M002/S02
- Validation: validated
- Notes: S03 proves via 14 automated tests (3 integration + 11 unit) and manual UAT that weekly scheduling workflows operate end-to-end through API, worker, and Telegram surfaces after M002 cleanup. Approval checkpoints, sync execution, and completion summaries all verified. UAT script in `.gsd/milestones/M002/slices/S03/S03-UAT.md` enables future verification.

### R004 — Non-core agents do not define current truth
- Class: constraint
- Status: active
- Description: EmailAgent and StudyAgent remain present, but their planning/spec/program artifacts do not define the current-version truth set; StudyAgent is frozen for this version, and Helm-level email planning artifacts are de-scoped as canonical truth.
- Why it matters: Keeps the milestone focused on the workflow-engine truth set and prevents agent-specific plans from quietly steering architecture.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S02
- Validation: proofed
- Notes: `.gsd/milestones/M002/M002-TRUTH-NOTE.md` (M002/S01) explicitly treats TaskAgent/CalendarAgent as core truth and EmailAgent/StudyAgent as non-core/frozen; classification rules and inventory in M002 reference this constraint.

## Deferred

### R020 — Additional workflows beyond scheduling
- Class: primary-user-loop
- Status: deferred
- Description: Running additional domain workflows (for example email flows, study flows, or other templates) on the same kernel contract.
- Why it matters: Expands Helm’s capabilities once the truth set is clean, but should not start until M002 has reduced the working set.
- Source: execution
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Seeded from prior M001/M002 vision; will be mapped in a later milestone.

## Out of Scope

### R030 — New primary dashboards or web UIs
- Class: anti-feature
- Status: out-of-scope
- Description: Building a new primary dashboard or web UI that replaces Telegram as the main operator surface.
- Why it matters: Prevents scope creep away from the kernel and task/calendar flows during cleanup.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Telegram remains the primary operator surface for this version.

## Traceability

| ID   | Class              | Status    | Primary owner | Supporting         | Proof      |
|------|--------------------|-----------|---------------|--------------------|------------|
| R001 | core-capability    | active    | M002/S01      | none               | proofed    |
| R002 | continuity         | validated | M002/S02      | M002/S01, M002/S03 | validated  |
| R003 | continuity         | validated | M002/S03      | M002/S01, M002/S02 | validated  |
| R004 | constraint         | active    | M002/S01      | M002/S02           | proofed    |
| R005 | failure-visibility | validated | M002/S02      | M002/S01           | validated  |
| REQ-DURABLE-PERSISTENCE | core-capability | validated | M001/S01 | none | validated |
| REQ-SPECIALIST-DISPATCH | integration     | validated | M001/S02 | none | validated |
| REQ-APPROVAL-CHECKPOINTS | core-capability | validated | M001/S02 | none | validated |
| REQ-ADAPTER-SYNC        | continuity      | validated | M001/S03 | none | validated |
| REQ-REPRESENTATIVE-WORKFLOW | primary-user-loop | validated | M001/S04 | none | validated |
| REQ-OPERATOR-SURFACES   | operability     | validated | M001/S04 | none | validated |
| R020 | primary-user-loop | deferred  | none          | none               | unmapped   |
| R030 | anti-feature      | out-of-scope | none        | none               | n/a        |

## Coverage Summary

- Active requirements: 2 (R001, R004)
- Validated: 10 (kernel requirements from M001 plus M002/S02 coverage for R002 and R005, plus M002/S03 coverage for R003)
- Deferred: 1
- Out of scope: 1
