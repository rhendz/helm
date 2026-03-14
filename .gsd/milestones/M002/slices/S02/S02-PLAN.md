S02: Repo cleanup and deprecation enforcement

**Goal:** Apply the M002 truth note and classification rules to the repo tree so deprecated/aspirational artifacts (LinkedIn, Night Runner, `packages/domain`, stale docs/tests) are physically removed or quarantined, while keeping EmailAgent/StudyAgent present but non-truth-defining and preserving the workflow-engine core.

**Demo:** On this slice branch, the tree no longer contains live LinkedIn and Night Runner integrations or an active `packages/domain` layer, deprecated docs/runbooks/specs are pruned or clearly quarantined, EmailAgent/StudyAgent remain present but narrowed per truth-set constraints, and tests/CI configs have been updated so the remaining suite passes focused on the workflow-engine and task/calendar flows.

## Must-Haves

- LinkedIn connector code, Night Runner runbooks/app entries, and `packages/domain` are either removed or moved under an explicit quarantine path, with their status and rationale captured in the M002 classification inventory.
- Tests/CI configs referring to removed or deprecated paths are either updated to target the workflow-engine truth set or removed alongside the deprecated behavior, with remaining tests passing locally.
- EmailAgent and StudyAgent code/storage/runtime remain present but have no newly-added dependencies or truth-defining docs; any removed or trimmed email/study artifacts are reflected in the classification inventory and key docs.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: no (reserved for S03; this slice relies on automated tests and targeted commands).

## Verification

- `pytest -q tests/unit tests/integration` on this branch passes, with no tests referencing removed LinkedIn, Night Runner, or `packages/domain` paths.
- `rg "linkedin" .` and `rg "night runner" .` only match within quarantined docs/notes or the classification inventory, not in live code or active runbooks.
- `python -m compileall .` (or equivalent type/check command) succeeds without import errors from removed/quarantined modules.

## Observability / Diagnostics

- Runtime signals: Rely on existing workflow/orchestration logs and test failure output; this slice does not introduce new runtime behavior, only trims deprecated surfaces.
- Inspection surfaces: `pytest` output, `rg` scans for deprecated symbols, and git diff for removed/quarantined paths.
- Failure visibility: Failing tests or import errors will indicate a missed dependency on removed/quarantined artifacts; classification inventory and grep results will help localize gaps.
- Redaction constraints: No secrets involved; ensure removed configs/docs do not contain credentials before deletion.

## Integration Closure

- Upstream surfaces consumed: `.gsd/milestones/M002/M002-TRUTH-NOTE.md`, `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`, `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`, `.gsd/REQUIREMENTS.md`, `.gsd/PROJECT.md`.
- New wiring introduced in this slice: Updated tests/CI configs that focus on the workflow-engine truth set and updated classification inventory entries describing removed/quarantined artifacts.
- What remains before the milestone is truly usable end-to-end: S03 must run end-to-end task/calendar workflows via API/worker/Telegram and author a UAT script to prove behavior after cleanup.

## Tasks

- [x] **T01: Map and confirm deprecated/quarantine targets against live usage** `est:45m`
  - Why: Ensure LinkedIn, Night Runner, `packages/domain`, and deprecated Email/Study surfaces can be safely removed or quarantined without breaking the workflow-engine truth set.
  - Files: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`, `.gsd/milestones/M002/M002-TRUTH-NOTE.md`, `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`, `pyproject.toml`, `tests/`, `packages/`, `apps/`, `docs/`
  - Do: Use ripgrep and static inspection to map imports and references to LinkedIn, Night Runner, `helm_domain`, and deprecated Email/Study artifacts across code, docs, tests, and CI; refine the classification inventory at module/file granularity and note any surprising couplings that will constrain cleanup.
  - Verify: `rg "helm_domain|linkedin|night runner|Night Runner" .` shows only expected references and updated inventory notes; no obviously missed high-level usage paths remain.
  - Done when: There is an updated, file-level classification inventory that clearly lists what will be removed vs quarantined in T02/T03, and no unknown dependencies on deprecated targets remain.

- [x] **T02: Physically remove or quarantine LinkedIn, Night Runner, and domain layer artifacts** `est:1h15m`
  - Why: Reduce the repo working set (R002, R005) by deleting or quarantining clearly-deprecated integrations and aspirational domain layers, aligned with the refined inventory.
  - Files: `packages/connectors/src/helm/connectors/linkedin/`, `docs/runbooks/night-runner*.md`, any `apps/night-runner` or Night Runner scripts, `packages/domain/`, `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`, `docs/internal/helm-v1.md`, `.gitignore`
  - Do: Remove or move to a quarantine namespace the LinkedIn connector module and tests, Night Runner runbooks/app/scripts, and `packages/domain` (or its modules) per T01’s map; update docs and classification inventory to reflect removals and ensure imports/entrypoints referencing these paths are cleaned up.
  - Verify: `pytest -q tests/unit tests/integration` passes after removals (modulo Email/Study-specific tests to be handled in T03); `rg "linkedin" .`, `rg "night runner" .`, and `rg "helm_domain" .` only hit quarantine docs/inventory; `python -m compileall .` has no missing-module errors for removed paths.
  - Done when: Deprecated LinkedIn, Night Runner, and domain artifacts no longer exist as live code/runbooks, and the repo still imports and tests successfully with updated docs/inventory.

- [x] **T03: Trim deprecated Email/Study artifacts and align tests/CI with the truth set** `est:1h30m`
  - Why: Keep EmailAgent/StudyAgent present but non-truth-defining (R004) while ensuring tests/CI focus on the workflow-engine and task/calendar flows and do not enforce deprecated behavior.
  - Files: `packages/storage/src/helm_storage/models.py`, `packages/storage/src/helm_storage/repositories/email_agent_config.py`, `packages/runtime/src/helm_runtime/email_agent.py`, `apps/worker/src/helm_worker/jobs/email_message_ingest.py`, `tests/unit/test_storage_repositories.py`, `tests/unit/test_email_followup.py`, CI config files (e.g., `.github/workflows/*.yml` or local scripts), `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`, `docs/internal/helm-v1.md`
  - Do: Identify and remove or quarantine non-essential Email/Study planning/spec/docs while retaining minimal runtime/config/storage contracts; update or remove tests that enforce deprecated email behavior, and adjust CI configs to drop checks tied to removed tests or apps; update classification inventory and docs to reflect the narrowed Email/Study status.
  - Verify: `pytest -q tests/unit tests/integration` passes with Email/Study artifacts present but no tests requiring deprecated email flows; CI config (locally inspectable) no longer references removed tests/apps; docs and inventory accurately describe EmailAgent as deprecated and StudyAgent as frozen.
  - Done when: EmailAgent and StudyAgent remain in the tree with minimal, non-truth-defining surfaces; tests and CI configs are aligned with the workflow-engine truth set; and all slice-level verification commands in this plan succeed.

## Files Likely Touched

- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`
- `packages/connectors/src/helm/connectors/linkedin/`
- `docs/runbooks/night-runner*.md`
- `packages/domain/`
- `docs/internal/helm-v1.md`
- `tests/unit/` and `tests/integration/`
- `packages/runtime/src/helm_runtime/email_agent.py`
- `apps/worker/src/helm_worker/jobs/email_message_ingest.py`
- CI configs under `.github/` or `scripts/` if present
