# Requirements

## Validated

- **REQ-DURABLE-PERSISTENCE**: Durable workflow runs, steps, artifacts, and lineage are persisted and inspectable — validated in M001 (S01 established core tables with typed repositories and hermetic test coverage).
- **REQ-SPECIALIST-DISPATCH**: Typed TaskAgent and CalendarAgent dispatch with durable invocation records — validated in M001 (specialist invocation table with input/output artifact linkage).
- **REQ-APPROVAL-CHECKPOINTS**: Approval checkpoints, revision-driven proposal versioning, and kernel-owned resume semantics — validated in M001.
- **REQ-ADAPTER-SYNC**: Adapter-gated sync execution with idempotency, retry, replay, and recovery classification — validated in M001.
- **REQ-REPRESENTATIVE-WORKFLOW**: Representative weekly scheduling workflow from request through approved writes and replay-aware final lineage — validated in M001.
- **REQ-OPERATOR-SURFACES**: Telegram and API operator tooling for workflow status, approval, replay, and lineage inspection — validated in M001.

## Active

### R001 — Helm workflow-engine truth set is sharply defined
- Class: core-capability
- Status: active
- Description: The current-version Helm truth set is explicitly defined around the workflow engine, replay/recovery/approvals, task/calendar sync protection, and the Telegram/API/worker surfaces that support those flows.
- Why it matters: Future milestones must not rely on stale, implicit, or aspirational artifacts to infer what Helm is; planning should start from a small, explicit truth set.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: none yet
- Validation: unmapped
- Notes: Truth set must be written down as a small note and reflected in classifications and requirements.

### R002 — Repo working set is reduced to active and frozen truth
- Class: continuity
- Status: active
- Description: Stale, misleading, or aspirational artifacts (code, docs, specs, tests, runbooks) that are not part of the current truth set are removed or explicitly marked deprecated/archived so they stop shaping future GSD decisions.
- Why it matters: Reduces cognitive load and prevents future work from building on dead paths just because files remain in the tree.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S01, M002/S03
- Validation: unmapped
- Notes: Bias toward physical removal; quarantine only with concrete justification.

### R003 — Task/calendar workflows remain intact and verified after cleanup
- Class: continuity
- Status: active
- Description: After truth-set cleanup and artifact removal, the representative weekly scheduling / task+calendar workflows continue to operate correctly through API/worker/Telegram, with explicit verification/UAT demonstrating no regressions.
- Why it matters: Task/calendar sync protection is core truth; cleanup must not break existing behavior.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S01, M002/S02
- Validation: unmapped
- Notes: Verification should reuse and, if needed, extend existing tests and runbooks for workflow runs.

### R004 — Non-core agents do not define current truth
- Class: constraint
- Status: active
- Description: EmailAgent and StudyAgent remain present, but their planning/spec/program artifacts do not define the current-version truth set; StudyAgent is frozen for this version, and Helm-level email planning artifacts are de-scoped as canonical truth.
- Why it matters: Keeps the milestone focused on the workflow-engine truth set and prevents agent-specific plans from quietly steering architecture.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S02
- Validation: unmapped
- Notes: EmailAgent code is left alone; email cleanup is about deprecating non-kernel truth surfaces.

### R005 — Deprecated paths are clearly marked and removed where safe
- Class: failure-visibility
- Status: active
- Description: LinkedIn, Night Runner, and underdeveloped aspirational layers (for example `packages/domain`) are explicitly classified as deprecated and physically removed where they are not required for current truth or behavior.
- Why it matters: Prevents future milestones from seeing these paths as live options and reduces risk of accidentally reviving deprecated architecture.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S01
- Validation: unmapped
- Notes: Quarantine/archive only when removal would cause concrete confusion or break necessary reference.

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

| ID   | Class            | Status   | Primary owner | Supporting         | Proof      |
|------|------------------|----------|---------------|--------------------|------------|
| R001 | core-capability  | active   | M002/S01      | none               | unmapped   |
| R002 | continuity       | active   | M002/S02      | M002/S01, M002/S03 | unmapped   |
| R003 | continuity       | active   | M002/S03      | M002/S01, M002/S02 | unmapped   |
| R004 | constraint       | active   | M002/S01      | M002/S02           | unmapped   |
| R005 | failure-visibility | active | M002/S02      | M002/S01           | unmapped   |
| REQ-DURABLE-PERSISTENCE | core-capability | validated | M001/S01 | none | validated |
| REQ-SPECIALIST-DISPATCH | integration     | validated | M001/S02 | none | validated |
| REQ-APPROVAL-CHECKPOINTS | core-capability | validated | M001/S02 | none | validated |
| REQ-ADAPTER-SYNC        | continuity      | validated | M001/S03 | none | validated |
| REQ-REPRESENTATIVE-WORKFLOW | primary-user-loop | validated | M001/S04 | none | validated |
| REQ-OPERATOR-SURFACES   | operability     | validated | M001/S04 | none | validated |
| R020 | primary-user-loop | deferred | none          | none               | unmapped   |
| R030 | anti-feature      | out-of-scope | none        | none               | n/a        |

## Coverage Summary

- Active requirements: 5
- Mapped to slices: 5
- Validated: 6 (kernel requirements from M001)
- Unmapped active requirements: 0
