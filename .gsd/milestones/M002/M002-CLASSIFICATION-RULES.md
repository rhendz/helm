# M002 Classification Rules — Workflow-Engine Truth Set

## Purpose

This note defines how Helm artifacts are classified for M002 in relation to the workflow-engine truth set defined in `.gsd/milestones/M002/M002-TRUTH-NOTE.md`.

It is the contract S02/S03 and future milestones use when deciding what to keep, freeze, deprecate, remove, or quarantine.

All rules are grounded in:
- The M001 kernel (durable workflow runs/steps/artifacts/events, orchestration, approvals, adapter-gated sync, replay/recovery)
- The representative weekly scheduling workflow
- TaskAgent and CalendarAgent as the only truth-defining agents for this milestone

If an artifact appears to conflict with these rules, **the kernel + representative workflow win**; this document should then be amended.

## Status Definitions

Statuses are defined in terms of the workflow-engine truth set and M002 cleanup goals.

### keep

**Definition:**
Artifacts that are *part of the current workflow-engine truth set* or are necessary support code/docs/tests for that truth. They remain active, are candidates for further investment, and should be kept accurate.

**Criteria:**
- Directly implement or exercise the M001 kernel contracts (runs, steps, artifacts, approvals, sync, replay).
- Are required for the representative weekly scheduling / task+calendar workflows through API/worker/Telegram.
- Are used by TaskAgent/CalendarAgent in their truth-defining flows.

**Examples:**
- `packages/storage` workflow tables and repositories used by the kernel (e.g., `workflow_runs`, `workflow_steps`, `workflow_artifacts`, `workflow_events`).
- `packages/orchestration` state machine and services that advance workflow steps, manage approvals, and handle replay.
- API workflow routes in `apps/api` and Telegram workflow commands in `apps/telegram-bot` that surface status, approvals, and replay for the representative weekly scheduling workflow.

### freeze

**Definition:**
Artifacts that are **not part of the current truth set**, but are kept in place in a read-only, non-evolving state because they may be needed later for reference or continuity. They must not drive new architectural decisions or be extended without explicit reclassification.

**Criteria:**
- Referenced by the truth note as non-core or frozen, or
- Provide useful historical context or potential future value, but are not required for current workflows.

**Behavioral rules:**
- No new features or dependencies should be added.
- Bugs are fixed only when they impact core truth or cleanup (e.g., to unblock removal of adjacent dead code).
- Documentation should clearly mark them as frozen.

**Examples:**
- **StudyAgent**: explicit frozen status in the truth note. Its prompts/specs remain for reference but do not define current behavior.
- Historical docs describing multi-agent futures that still provide context but are not part of the M002 truth set.

### deprecate

**Definition:**
Artifacts that are **actively being phased out** because they are not part of the truth set and have better replacements or are no longer aligned with the product direction. They may still be wired in, but callers should be steered away and follow-up work should remove or refactor them.

**Criteria:**
- Not required for the representative weekly scheduling workflow or the M001 kernel.
- Still in use or wired up in ways that would require some refactor or migration to fully remove.

**Behavioral rules:**
- Marked clearly as deprecated in code/docs.
- New usage is discouraged; new code should not depend on them.
- S02/S03 should either remove them or convert them to keep/freeze/quarantine with justification.

**Examples:**
- Old helper modules for legacy scheduling flows that are still referenced but superseded by the kernel-based workflow engine.
- Early versions of adapter protocols that have a newer, kernel-aligned implementation.

### remove

**Definition:**
Artifacts that are **safe to delete** in M002 because they are not part of the truth set, are not needed for the representative weekly scheduling workflow, and do not provide critical historical or diagnostic value.

**Criteria:**
- Not used by the M001 kernel, representative weekly scheduling workflow, or TaskAgent/CalendarAgent.
- Not required for repository health (tests, tooling, CI) and not needed as a diagnostic reference.
- Deleting them does not change any behavior covered by existing tests or runbooks for the kernel and representative workflow.

**Behavioral rules:**
- Prefer physical deletion over soft flags when safe.
- If in doubt, move to quarantine instead of partial deletion.

**Examples:**
- Unused experimental scripts that were never wired into the kernel or operator surfaces.
- Dead test fixtures for flows that no longer exist and are not the representative workflow.

### quarantine

**Definition:**
Artifacts that are **non-truth** but are retained in a clearly marked area because immediate removal would cause confusion or lose valuable reference material. Quarantine is a **temporary, deliberate holding pen**, not a default.

**Criteria:**
- Not part of the truth set, but provide:
  - complex reference implementations, or
  - non-trivial planning that might be reused later.
- Removal in M002 would make it materially harder to understand how we got to the current kernel or to design future kernels.

**Behavioral rules:**
- Moved or grouped into clearly named quarantine/legacy locations where feasible.
- Documented with a short note explaining why they are quarantined instead of removed.
- Future milestones must either promote to keep/freeze or remove entirely.

**Examples:**
- Historical end-to-end workflows built on pre-M001 assumptions that still offer design insight.
- Rich but non-truth runbooks that explain now-deprecated operator paths.

## Agent and Integration Treatment

The truth note already establishes TaskAgent and CalendarAgent as the only core agents for M002 and calls out several non-core integrations. This section binds them to explicit statuses for cleanup.

### Core Agents (TaskAgent, CalendarAgent)

- **Status:** keep
- **Rationale:** They are the only agents whose behavior defines the current truth set. Their contracts and integration with the kernel must remain intact and may be refined.

### EmailAgent

- **Status:** deprecate → remove or quarantine (S02 decision)
- **Rationale:**
  - Email flows are explicitly de-scoped as canonical truth in the M002 truth note.
  - Existing EmailAgent code and planning artifacts do not define the current workflow-engine truth.
- **Expected treatment:**
  - Mark EmailAgent paths and email planning docs as deprecated.
  - In S02, either:
    - remove unused email flows and wiring, or
    - move them into a clearly marked quarantine/legacy area if they contain useful reference material.

### StudyAgent

- **Status:** freeze
- **Rationale:**
  - The truth note explicitly calls StudyAgent frozen for this version.
  - It may be useful for future workflows, but M002 must not extend or rely on it for kernel decisions.
- **Expected treatment:**
  - Label StudyAgent specs, prompts, and planners as frozen.
  - Do not add new dependencies from kernel or operator paths to StudyAgent.

### LinkedIn Integrations

- **Status:** deprecate → remove or quarantine (S02 decision)
- **Rationale:**
  - The truth note lists LinkedIn as explicitly non-truth.
  - LinkedIn flows do not participate in the representative weekly scheduling workflow.
- **Expected treatment:**
  - Mark LinkedIn-related code and docs as deprecated.
  - S02 should preferentially remove them; quarantine only if they provide needed reference.

### Night Runner and Experimental Cron-like Flows

- **Status:** deprecate → remove or quarantine (S02 decision)
- **Rationale:**
  - Night Runner and similar experimental/cron flows are explicitly outside the truth set.
  - They are not required for the kernel or representative workflow.
- **Expected treatment:**
  - Mark Night Runner and related flows as deprecated.
  - Plan to remove or quarantine them in S02, ensuring no required tests or workflows depend on them.

### `packages/domain`

- **Status:** quarantine (default), with selective keep/remove
- **Rationale:**
  - The truth note calls out `packages/domain` as an underdeveloped aspirational layer.
  - Some concepts may be useful for future work, but it is not part of the M002 truth set.
- **Expected treatment:**
  - Treat the package as quarantined by default: not authoritative, not extended.
  - S02 may:
    - promote specific low-level pieces to **keep** if they are actively used by the kernel or representative workflow, or
    - remove unused parts that add confusion without reference value.

## How to Use These Rules in S02/S03

- **S02 (cleanup):**
  - Use these status definitions to classify major modules, docs, tests, and integrations.
  - Bias toward **remove** when an artifact is non-truth and clearly unused.
  - Use **freeze** and **quarantine** sparingly, with written rationale.

- **S03 (verification):**
  - Confirm that keep/freeze/quarantine artifacts do not contradict the truth note.
  - Ensure that task/calendar workflows and operator surfaces still operate correctly after deprecate/remove changes.

When in doubt, align with:
- `.gsd/milestones/M002/M002-TRUTH-NOTE.md` for what defines truth.
- This file for how non-truth artifacts should be treated.
