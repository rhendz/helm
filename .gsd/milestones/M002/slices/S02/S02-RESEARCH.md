# S02 — Research: Repo cleanup and deprecation enforcement

**Date:** 2026-03-13

## Summary

S02 sits on top of a now-explicit workflow-engine truth set and a coarse classification inventory. Its job is to turn that contract into concrete tree changes: physically remove or quarantine deprecated/aspirational paths (EmailAgent planning surfaces, LinkedIn, Night Runner, `packages/domain`, stale docs/runbooks/tests) while preserving the weekly scheduling / task+calendar workflow and its kernel.

The main research outcome: S02 should treat `packages/storage`, `packages/orchestration`, `packages/runtime`, `packages/llm`, `packages/connectors` (minus LinkedIn), `apps/api`, `apps/worker`, `apps/telegram-bot`, and the integration/unit tests that exercise the representative weekly scheduling flow as **hard keep**. EmailAgent and its config/runtime/storage are **deprecate** but still wired through runtime and tests; they need coordinated removal or quarantine plus test updates rather than one-off deletes. `packages/domain` is small and currently unused by core flows; it is safe to quarantine or even remove entirely once usage scans are confirmed. LinkedIn and Night Runner live mostly in docs/runbooks and (for LinkedIn) a connector subpackage; they can be removed/quarantined after verifying tests don’t depend on them. The core risk is deleting or modifying something that currently underpins the storage/runtime contracts for EmailAgent or that accidentally touches task/calendar workflow behavior.

## Recommendation

S02 should be executed as a **dependency-guided cleanup** rather than a big-bang delete:

1. **Anchor to requirements:**
   - R002 (reduce working set to active/frozen truth) and R005 (deprecated paths clearly marked/removed) are the primary owners for this slice. Their success criteria translate to: (a) deprecated and aspirational packages are physically removed or quarantined, and (b) what remains is either core truth or explicit frozen reference.

2. **Map and protect core flows first:**
   - Treat the weekly scheduling / task+calendar workflow and its kernel/storage/runtime wiring as immutable for this slice. Before removing anything, make sure tests covering orchestration, storage, connectors (task/calendar), and integration flows for scheduling stay green.
   - Use the existing classification inventory as a whitelist: anything tagged `keep` is presumed in-scope for those tests and must not be removed or heavily refactored in S02.

3. **Triage deprecated/quarantine candidates by coupling:**
   - **EmailAgent:** The inventory marks `packages/agents/src/helm/agents/email_agent` as `deprecate`, but `rg` shows a significant dependency surface (storage models and repositories, runtime wiring, worker jobs, and unit tests). S02 should:
     - Keep core storage/repository contracts (`EmailAgentConfigORM`, `EmailAgentConfigRepository`, `SQLAlchemyEmailAgentConfigRepository`) and tests intact for now.
     - Remove or quarantine *planning/spec* surfaces (email-focused docs, runbooks, prompts) and non-essential jobs first.
     - Optionally narrow EmailAgent to a minimal supported runtime while keeping its config repository, marking this state in the classification inventory.
   - **StudyAgent:** Marked `freeze`; do not expand or deepen dependencies. Quarantine/remove only obvious dead docs; avoid touching the app/runtime wiring.
   - **LinkedIn:** Remove the `packages/connectors/src/helm/connectors/linkedin` module and any LinkedIn-specific tests if they are not referenced from the representative workflow. If they are only unit-level, reclassify them as deprecated and decide whether to remove or quarantine after verifying no higher-level flows need them.
   - **Night Runner:** Remove or quarantine `docs/runbooks/night-runner*.md` and any `apps/night-runner` or `scripts` entries if they exist. Ensure no tests rely on Night Runner as a proxy for kernel scheduling.
   - **Domain layer:** Given the tiny surface (`packages/domain/README.md`, `src/helm_domain/models.py`, `__init__.py`) and no obvious references from orchestrator/storage/runtime, it is safe to treat `packages/domain` as a quarantine/remove candidate. S02 should confirm via `rg "helm_domain"` and then either remove the package or move it under a quarantined path and update the inventory accordingly.

4. **Refine tests and CI around the truth set:**
   - Scan `tests/unit` and `tests/integration` for references to deprecated agents or integrations (EmailAgent, StudyAgent, LinkedIn, Night Runner, `helm_domain`). Decide test-by-test whether they:
     - Protect core workflow contracts (keep, but possibly refactor to remove deprecated dependencies), or
     - Encode deprecated architecture (remove or freeze alongside the code).
   - Update CI configs to stop treating removed tests/apps as required checks.

5. **Keep documentation aligned with the trimmed tree:**
   - For each deleted or quarantined path, update `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` with per-module granularity (e.g., `packages/connectors/src/helm/connectors/linkedin` → removed, tests adjusted) and adjust docs (especially `docs/internal/helm-v1.md` and `docs/runbooks`) so they don’t advertise removed integrations as live.

This approach reduces risk of breaking core flows while aggressively collapsing the working set around the truth note. It also keeps the classification inventory as the single entry point for what was removed, what is frozen, and why.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Persisting and querying workflow runs, approvals, artifacts, and sync records | `packages/storage` repositories and models | Already vetted by M001, tightly coupled to orchestration and operator surfaces; changing persistence abstractions in S02 would risk regressions far beyond cleanup scope. |
| Workflow orchestration, replay, and recovery | `packages/orchestration` and existing services/state machine | Encodes all M001 decisions; S02 should only touch references to deprecated agents/integrations, not reimplement orchestration logic. |
| EmailAgent configuration storage and runtime wiring | `EmailAgentConfigORM`, `EmailAgentConfigRepository`, `HelmEmailAgentRuntime` | Even though EmailAgent is deprecated, these contracts exist and are used by tests and runtime; S02 should reuse/minimize them rather than inventing new config surfaces. |
| Connectors and adapter-gated sync | `packages/connectors` (non-LinkedIn connectors) | Provides the adapter abstraction aligned with REQ-ADAPTER-SYNC; S02 should prune unused connectors, not build new sync mechanisms. |

## Existing Code and Patterns

- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — Coarse-grained classification inventory that S02 should refine into per-module/file statuses (keep/freeze/deprecate/remove/quarantine).
- `packages/connectors/src/helm/connectors/linkedin` — LinkedIn connector path marked `deprecate`; a concrete target for removal or quarantine once tests and dependencies are analyzed.
- `docs/runbooks/night-runner*.md` and any `apps/night-runner` / `scripts` entries — Night Runner artifacts explicitly tagged `deprecate`; they should be removed or moved under a quarantined docs path.
- `packages/domain/src/helm_domain/` — Underdeveloped domain layer (README, models, `__init__`) tagged `quarantine`; S02 can validate that `helm_domain` is unused by core workflows and then either remove or relocate it under a quarantine namespace.
- `packages/storage/src/helm_storage/models.py` and `repositories/email_agent_config.py` — Storage models and repositories for EmailAgent configuration; heavily referenced from runtime and tests, so they are a coupling constraint when trimming EmailAgent surfaces.
- `packages/runtime/src/helm_runtime/email_agent.py` — Runtime wrapper that wires EmailAgent into SQLAlchemy storage; important for understanding how tightly EmailAgent is entangled with core runtime.
- `apps/worker/src/helm_worker/jobs/email_message_ingest.py` — Worker job using `EmailAgentRuntime`; an example of how EmailAgent is surfaced in the job system and a candidate for deprecation/quarantine treatment.
- `tests/unit/test_storage_repositories.py` and `tests/unit/test_email_followup.py` — Unit tests that exercise EmailAgent storage and behavior; useful for verifying that any trimming of EmailAgent is done safely (or for removal of tests alongside deprecated behavior).

## Constraints

- **Hard:** S02 must not break the representative weekly scheduling / task+calendar workflow or any kernel behavior validated in M001. This means `packages/storage`, `packages/orchestration`, `packages/runtime` (non-email portions), `packages/llm`, `packages/connectors` (task/calendar adapters), and `apps/api` / `apps/worker` / `apps/telegram-bot` are effectively immutable aside from dependency cleanup and deprecation tagging.
- **Hard:** R002 and R005 require bias toward physical removal over soft deprecation; freeze/quarantine should be used sparingly, with clear rationale captured in the inventory.
- **Hard:** EmailAgent and StudyAgent must remain present (R004), but EmailAgent is deprecated and StudyAgent is frozen; S02 cannot repurpose them as part of the truth set or introduce new dependencies on them.
- **Dependency:** Tests and CI currently encode assumptions about EmailAgent config repositories and possibly LinkedIn/Night Runner; S02 must update or remove those tests as part of cleanup rather than leaving them failing.
- **Dependency:** `docs/internal/helm-v1.md` and key runbooks are considered primary product/spec references; any removal of referenced components should be paired with doc updates.

## Common Pitfalls

- **Deleting shared storage/runtime primitives along with deprecated agents/integrations** — EmailAgent’s storage contracts and runtime wiring are used by tests and may be entangled with generic runtime utilities. Before removing, verify references via `rg` and refactor toward minimal, clearly-deprecated surfaces rather than wholesale deletion.
- **Leaving tests as the only remaining surface for deprecated behavior** — Removing code but leaving tests that still reference it will both break CI and mislead future slices about what’s still “live.” When removing or quarantining behavior, update or remove the associated tests and reflect the change in the classification inventory.
- **Overusing quarantine/freeze to avoid hard decisions** — The classification rules bias toward physical removal. If a path is not required for representative workflows and has no clear future plan, prefer `remove` over `quarantine`, and document any exceptions.
- **Subtly breaking task/calendar flows via doc or runbook edits** — Some runbooks and docs are used as operational reference for the weekly scheduling workflow. When trimming docs, ensure that task/calendar-oriented runbooks stay intact and accurate.

## Open Risks

- Hidden coupling between EmailAgent components and core runtime or orchestration that isn’t obvious from static searches; aggressive removal could surface runtime errors outside the test set.
- LinkedIn or Night Runner concepts implicitly referenced in prompts, runbooks, or operator expectations; removing them without clear doc updates could create confusion for future slices.
- Under-documented use of `packages/domain` in any emerging or experimental tests not covered by current search patterns.
- CI configuration or scripts that assume the presence of certain apps (e.g., Night Runner) or tests tied to deprecated agents/integrations.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI / worker orchestration | (skills search via `npx skills find "FastAPI"`) | available (candidate skills exist; user can install if deeper FastAPI guidance is needed) |
| SQLAlchemy / Postgres persistence | (skills search via `npx skills find "SQLAlchemy"`) | available (candidate skills exist; user can install to deepen ORM/persistence work if needed) |
| Helm internal debugging | ~/.gsd/agent/skills/debug-like-expert | available (already installed; use when cleanup exposes non-obvious runtime/test failures) |

## Sources

- Active requirements R002 (Repo working set reduced to active/frozen truth) and R005 (Deprecated paths clearly marked and removed where safe) — source: `.gsd/REQUIREMENTS.md`.
- Classification inventory and rules providing cleanup targets and semantics — source: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` and `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`.
- EmailAgent config and runtime wiring, plus tests — source: `packages/storage/src/helm_storage/models.py`, `packages/storage/src/helm_storage/repositories/email_agent_config.py`, `packages/runtime/src/helm_runtime/email_agent.py`, `apps/worker/src/helm_worker/jobs/email_message_ingest.py`, `tests/unit/test_storage_repositories.py`, and `tests/unit/test_email_followup.py`.
- Domain layer footprint — source: `packages/domain/README.md`, `packages/domain/src/helm_domain/models.py`, `packages/domain/src/helm_domain/__init__.py`.
- LinkedIn and Night Runner artifact locations — source: `packages/connectors/src/helm/connectors/linkedin`, `docs/internal/helm-v1.md`, `docs/runbooks/night-runner.md`, and `docs/runbooks/night-runner-prompt.md`.
