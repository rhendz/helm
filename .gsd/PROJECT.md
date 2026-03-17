# Project

## What This Is

Helm is a single-user personal AI orchestration system, Telegram-first and DB-first. It runs multi-step, approval-gated workflows that connect operator intent to real external systems (Google Calendar, task storage). The core operator loop is: send a task or scheduling request via Telegram → Helm infers semantics → creates internal records → syncs to Calendar → notifies when done.

## Core Value

The operator can add a task through Telegram and trust that it lands on Calendar at the right time, with correct local timezone, without requiring the operator to debug internal state or poll for status.

## Current State

- M001–M003 complete: durable workflow kernel, truth-set cleanup, real Google Calendar OAuth integration with drift detection.
- M004 in progress (S01–S04 complete, S05–S06 remaining):
  - S01–S03: `/task` quick-add with LLM inference, shared timezone/scheduling primitives, immediate execution path all shipped.
  - S04: `/status` (pending approvals with `/approve N M` hints, recent completions, OPERATOR_TIMEZONE) and `/agenda` (today's Calendar events in local time) commands live; proactive approval notifications wired into worker; 501 tests passing.
- Remaining: S05 (real E2E calendar tests with staging calendar), S06 (live reload, Datadog, cleanup).

## Architecture / Key Patterns

- Python monorepo: `apps/` (api, worker, telegram-bot) and `packages/` (orchestration, storage, connectors, agents, llm, observability, runtime).
- DB-first: Postgres is the source of truth for workflow state, artifacts, sync records, tasks.
- Custom step-runner in `packages/orchestration` — not LangGraph. Specialist steps registered in `apps/worker/jobs/workflow_runs.py`.
- Worker polls every 30s for runnable steps (target: reduce to background-only after M004 direct execution path).
- Telegram bot is the primary operator surface. Proactive push via `TelegramDigestDeliveryService` (bot.send_message) exists but is only used for digests today.
- Google Calendar adapter in `packages/connectors/src/helm_connectors/google_calendar.py` — correct RFC3339 formatting, but no operator timezone awareness upstream.
- LLM via `packages/llm` (OpenAI). Currently unused in the scheduling path — `_run_task_agent` is pure Python with no inference.
- `uv` for dependency management. `uv.lock` present.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract.

## Milestone Sequence

- [x] M001: Helm Orchestration Kernel v1 — Durable workflow kernel with weekly scheduling workflow and shared operator surfaces.
- [x] M002: Helm Truth-Set Cleanup — Strict workflow-engine truth set, removal of stale artifacts, verified task/calendar workflow protection.
- [x] M003: Task/Calendar Productionization — Real Google Calendar OAuth, drift detection, Telegram sync visibility, partial failure handling.
- [ ] M004: Foundation Repair — Fix the core task→calendar loop: correct timezone handling, LLM task inference, `/task` quick-add, immediate operator execution, Telegram UX overhaul, strict test boundaries with real E2E calendar coverage, live reload, Datadog.
- [ ] M005: Bidirectional Sync + Recurring Events — External calendar edit detection, internal reconciliation, conflict handling, recurring event support, reactive webhooks where viable.
