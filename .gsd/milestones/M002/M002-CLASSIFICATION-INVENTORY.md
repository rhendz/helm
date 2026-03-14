# M002 Classification Inventory — Refined S02/T01 Pass

## Purpose

This inventory applies the M002 workflow-engine truth note and classification rules to the Helm repo.
This S02/T01 refinement adds per-file/module entries for LinkedIn, Night Runner, `packages/domain`, and
Email/Study-related docs/specs/tests/runtime, so later tasks can safely remove or quarantine artifacts
without breaking the workflow-engine truth set or task/calendar workflows.

Statuses use the semantics from `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`:

- `keep`
- `freeze`
- `deprecate`
- `remove`
- `quarantine`

Each entry is tagged with a status and a short rationale tied to the workflow-engine truth set in
`.gsd/milestones/M002/M002-TRUTH-NOTE.md`.

## Summary by Status

- **keep**: Kernel tables and repositories, orchestration state machine, Task/Calendar agents, core
  API/worker/Telegram workflow surfaces, and the tests/docs that directly exercise the representative
  weekly scheduling workflow.
- **freeze**: StudyAgent app and its docs/specs; selected historical planning docs that are useful
  reference but not part of the current truth set.
- **deprecate**: EmailAgent and email-centric planning artifacts; LinkedIn integrations; Night
  Runner/cron-like experiments; legacy scheduling helpers that predate the kernel.
- **remove**: Clearly-unused experiments, scripts, fixtures, or docs not referenced by the kernel,
  representative workflow, or active runbooks.
- **quarantine**: `packages/domain` and rich but non-truth historical workflows/runbooks retained
  for design/reference.

## Inventory

### Kernel and Orchestration

- `packages/storage` — **keep**
  - Rationale: Hosts workflow_runs/steps/artifacts/events, approvals, and sync-related tables and
    repositories used by the M001 kernel.
- `packages/orchestration` — **keep**
  - Rationale: Contains the orchestration state machine and services that advance steps, manage
    approvals, and handle replay/recovery for the representative weekly scheduling workflow.
- `packages/runtime` — **keep**
  - Rationale: Runtime utilities supporting kernel execution and task/calendar workflows; evaluated
    as part of M001 kernel behavior.
- `packages/observability` — **keep**
  - Rationale: Logging/metrics/run-trace utilities needed to inspect and debug kernel and workflow
    behavior.

### Agents and Connectors

- `packages/agents/src/helm/agents/task_agent` — **keep**
  - Rationale: TaskAgent is a core truth-defining agent in M002.
- `packages/agents/src/helm/agents/calendar_agent` — **keep**
  - Rationale: CalendarAgent is a core truth-defining agent in M002.
- `packages/agents/src/helm/agents/email_agent` — **keep**
  - Rationale: EmailAgent code and runtime remain in place. Helm-level email planning/spec/program
    artifacts are non-canonical, but the agent code itself is present and functional for this version.
- `packages/agents/src/helm/agents/study_agent` — **freeze**
  - Rationale: StudyAgent is frozen per the truth note; no new dependencies, retained for reference.

#### EmailAgent runtime, storage, and worker wiring

- `packages/agents/src/email_agent/` — **keep**
  - Rationale: EmailAgent runtime/operator modules are present and functional. While email flows
    are not truth-defining, the agent runtime is part of the durable persistence layer.
- `packages/agents/src/email_agent/runtime.py` — **keep**
  - Rationale: Defines EmailAgentRuntime and EmailAgentConfigRecord used by storage, runtime,
    and worker jobs. These contracts remain in place for this version.
- `packages/runtime/src/helm_runtime/email_agent.py` — **keep**
  - Rationale: Helm-specific EmailAgentRuntime implementation bridges agents and storage for
    email flows. Present but non-truth-defining.
- `packages/storage/src/helm_storage/models.py` (EmailAgent-specific parts) — **keep**
  - Rationale: `EmailAgentConfigORM` model defines the `email_agent_configs` table referenced by
    storage repositories and tests. Even if EmailAgent flows are deprecated, the table/schema is part
    of the durable storage truth set for now.
- `packages/storage/src/helm_storage/repositories/contracts.py` (EmailAgent symbols) — **keep**
  - Rationale: `EmailAgentConfigPatch` and `EmailAgentConfigRepository` protocols are part of the
    storage contracts currently exercised by tests and runtime; they may be narrowed later but are
    not removed in S02.
- `packages/storage/src/helm_storage/repositories/email_agent_config.py` — **keep**
  - Rationale: Concrete SQLAlchemy repository for `EmailAgentConfigORM` used by
    `packages/runtime/src/helm_runtime/email_agent.py` and unit tests.
- `packages/storage/src/helm_storage/repositories/__init__.py` (EmailAgent exports) — **keep**
  - Rationale: Re-exports EmailAgent config repository symbols for callers; depends on email-related
    repositories above.
- `apps/worker/src/helm_worker/jobs/email_message_ingest.py` — **keep**
  - Rationale: Worker job for ingesting inbound email messages; present and functional.
    Non-truth-defining but part of the durable runtime.
- `apps/worker/src/helm_worker/jobs/email_reconciliation_sweep.py` — **keep**
  - Rationale: Worker sweep job for email reconciliation; present but non-truth-defining.
- `apps/worker/src/helm_worker/jobs/email_triage.py` — **keep**
  - Rationale: Worker job for email triage; present but non-truth-defining.

#### StudyAgent app surface

- `apps/study-agent` — **freeze**
  - Rationale: App-specific surface for StudyAgent; frozen alongside the agent per the truth note.
    No new dependencies should be added.

#### LinkedIn connectors

- `packages/connectors` — **keep** (package)
  - Rationale: Connector package is required for adapter-gated sync; individual connectors are
    classified per integration.
- `packages/connectors/src/helm_connectors` — **keep**
  - Rationale: Top-level connector package for concrete integrations. LinkedIn-specific modules
    within this package are candidates for deprecate/remove.
- `packages/connectors/src/helm_connectors/linkedin` (not present in tree) — **remove (logical)**
  - Rationale: The inventory and classification rules expect a LinkedIn connector. No such directory
    exists in the current tree, so the LinkedIn connector is treated as already removed. Future work
    should avoid reintroducing it without explicit reclassification.
  - Surprising coupling: None observed at code level; only the classification inventory referenced
    this path. S02/T02 should not assume additional LinkedIn cleanup beyond docs/notes if no new
    code appears.

### Domain Layer

- `packages/domain` — **remove**
  - Rationale: Underdeveloped aspirational layer with no active imports or usage. Removed during corrective pass.
  - Note: Removed from live code; diagnostics confirm zero imports.
- `scripts/run-api.sh` — **deprecate** (domain-related portion)
  - Rationale: Includes `packages/domain/src` in PYTHONPATH; no active imports rely on it.

### Night Runner and Experimental Cron-like Flows

- `scripts/night-runner.sh` — **remove**
  - Rationale: Non-truth experimental tooling. Removed during corrective pass.
- `scripts/install-night-runner-cron.sh` — **remove**
  - Rationale: Non-truth cron infrastructure for night runner. Removed during corrective pass.
- `docs/archive/night-runner.md` — **remove**
  - Rationale: Historical runbook for non-truth workstream. Removed during corrective pass.
- `docs/archive/night-runner-prompt.md` — **remove**
  - Rationale: Prompt for non-truth tool. Removed during corrective pass.

### Docs and Specs — Email/Study

- `docs/internal/email-agent-blocked-slices-and-decisions.md` — **deprecate**
  - Rationale: Internal note capturing EmailAgent decisions and blocked work. Valuable history but
    not part of the workflow-engine truth set; references EmailAgentConfig storage decisions.
- `docs/internal/email-agent-implementation-program.md` — **deprecate**
  - Rationale: Program document for EmailAgent implementation. Aspirational, non-truth; informs
    design but should not drive kernel decisions.
- `docs/internal/Email-Drafting-Workflow-Rubric.md` — **deprecate**
  - Rationale: Rubric for email drafting flows; non-truth integ.
- `docs/internal/Email-Labeling-Workflow-Rubric.md` — **deprecate**
  - Rationale: Rubric for email labeling flows; non-truth integ.
- `docs/internal/EmailAgentPolicy.md` (referenced, not present) — **remove (logical)**
  - Rationale: Several docs link to this policy file by absolute path, but it does not exist in the
    repo. Treated as an already-removed artifact; follow-up slices should avoid resurrecting it
    without explicit reclassification.
- `docs/internal/helm-v1.md` — **keep** (rewritten)
  - Rationale: Core architectural reference. Rewritten during M002 corrective pass to describe
    the current workflow-engine-centric truth set, replacing the older multi-agent product vision.

### Tests — Email/Study

- `tests/unit/test_email_followup.py` — **deprecate**
  - Rationale: Tests focused on EmailAgentConfig behavior and follow-up flows. Non-truth but
    currently exercise storage and runtime contracts; S02/S03 must decide whether to keep as
    reference, freeze, or remove when trimming email flows.
  - Surprising coupling: Uses `SQLAlchemyEmailAgentConfigRepository` and `EmailAgentConfigPatch`
    directly, tying email-specific storage contracts into the generic storage test suite.
- `tests/unit/test_storage_repositories.py` (EmailAgent sections) — **keep**
  - Rationale: Validates behavior of `EmailAgentConfigRepository` and backing ORM as part of storage
    contracts. Even if EmailAgent flows are deprecated, these tests ensure storage behavior remains
    coherent.
- `tests/integration` — **keep** (no direct email/study references found by targeted rg)
  - Rationale: Focus on workflow-engine kernel and task/calendar flows; any email/study tests would
    need additional classification if added later.

### Miscellaneous / Historical

- `docs/domain` — **quarantine**
  - Rationale: Domain design materials aligned with `packages/domain`; quarantined for design
    reference, not part of truth.
- `study-agent-v2*.md`, `study-agent-v3*.md` — **freeze**
  - Rationale: Historical StudyAgent design docs retained as frozen reference, not part of truth.

## Notes for S02/S03

- All files returned by `rg "night runner|night-runner" .`, `rg "helm_domain" .`, and targeted
  searches for email runtime/storage symbols are now represented in this inventory.
- LinkedIn is represented only in this inventory and classification rules; no concrete code or tests
  for LinkedIn exist in the current tree.
- The main risky couplings to respect when trimming deprecated surfaces are:
  - EmailAgent runtime/storage/worker wiring (`packages/agents/src/email_agent/*`,
    `packages/runtime/src/helm_runtime/email_agent.py`, storage repositories, and worker jobs).
  - Storage contracts (`EmailAgentConfigORM`, `EmailAgentConfigPatch`, `EmailAgentConfigRepository`)
    used both by runtime and unit tests.
- Later tasks (T02/T03) should:
  - Prefer removing or quarantining deprecated EmailAgent worker jobs and non-essential docs while
    preserving minimal storage/runtime contracts until tests and migrations are safely updated.
  - Treat quarantine/freeze entries as non-truth: they must not drive new architectural decisions
    without an explicit reclassification and inventory update.
