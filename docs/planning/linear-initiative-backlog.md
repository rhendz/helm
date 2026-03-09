# Linear Initiative Backlog (Helm V1)

This document is formatted so initiatives/issues can be copied into Linear with minimal editing.

## Initiative 1: Foundation + Storage Baseline

Goal: lock the DB-first foundation so other workflows can build safely.

Suggested issues:

1. Implement V1 SQLAlchemy entities from `docs/internal/helm-v1.md`.
2. Create Alembic baseline migration and verification tests.
3. Add repository interfaces for core artifact tables.
4. Add API/worker DB session lifecycle and health checks.

## Initiative 2: Email Triage Loop (Phase 2)

Goal: ingest and triage email into durable artifacts with draft generation.

Suggested issues:

1. Gmail connector ingest and message normalization.
2. Email triage LangGraph flow scaffold.
3. Thread classification + priority scoring policy.
4. Draft generation flow + storage wiring.
5. Retry and failed-run reprocess path.

## Initiative 3: Telegram Action Surface

Goal: make Telegram a practical operator UI for V1.

Suggested issues:

1. Implement `/actions` and `/drafts` data-backed handlers.
2. Implement `/approve <id>` and `/snooze <id>` command parsing.
3. Add allowed-user auth guard tests.
4. Add message formatting standards for concise command outputs.

## Initiative 4: Daily Digest (Phase 3)

Goal: deliver concise daily command briefing from artifacts.

Suggested issues:

1. Digest ranking query + prioritization rules.
2. Digest agent generation contract.
3. Worker scheduled digest trigger.
4. Telegram `/digest` and push delivery path.

## Initiative 5: Study Loop (Phase 4)

Goal: build continuity for study execution and weakness tracking.

Suggested issues:

1. Manual study ingest API endpoint finalization.
2. Study summarization and task extraction logic.
3. Knowledge gap storage + severity tracking.
4. Study-focused digest enrichment.

## Initiative 6: LLM + Prompt Contracts

Goal: stabilize model interactions as testable interfaces.

Suggested issues:

1. Prompt contract modules per workflow.
2. Structured output parsing + validation.
3. Model fallback/timeout policy.
4. Golden tests for prompt regressions.

## Initiative 7: Reliability + Observability

Goal: make failures visible and recoverable.

Suggested issues:

1. Agent run logging schema and writes.
2. Error classification and retry policy.
3. Admin reprocess endpoints.
4. Operator runbook for incident/debug loop.

## Initiative 8: LinkedIn Feasibility (Optional V1.x)

Goal: decide integration path or defer explicitly.

Suggested issues:

1. Evaluate ingest options + legal/operational constraints.
2. Implement manual ingest fallback path.
3. Define go/no-go decision with explicit criteria.

