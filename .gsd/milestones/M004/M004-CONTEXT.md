---
# no depends_on — M004 is independent, M001–M003 are already complete
---

# M004: Foundation Repair

**Gathered:** 2026-03-17
**Status:** Ready for planning

## Project Description

Helm is a single-user personal AI orchestration system. The operator interacts via Telegram. Helm creates tasks, infers scheduling semantics, and writes events to Google Calendar. The system is built on a custom DB-backed step runner (not LangGraph — that only appears in the deprecated email agent). Orchestration lives in `packages/orchestration`, connectors in `packages/connectors`, storage models in `packages/storage`, Telegram bot in `apps/telegram-bot`, worker in `apps/worker`.

## Why This Milestone

The core loop — Telegram → task → Calendar — is functionally broken in specific, concrete ways:

1. **Timezone is wrong.** `_candidate_slots` in `apps/worker/src/helm_worker/jobs/workflow_runs.py:329` has `base = datetime(2026, 3, 16, 9, tzinfo=UTC)` — hardcoded date, UTC interpretation of local times. "Monday 10am" becomes UTC 10am, which lands as 3am PDT. This is the root cause of the calendar bug the operator observed.
2. **Task inference is a stub.** `_run_task_agent` is pure Python with no LLM call. Urgency, priority, and sizing are either omitted or defaulted. There is no semantic understanding of "need to book flights this week."
3. **No fast entry path.** The only way to add a task is `/workflow_start` which launches the full weekly scheduling workflow. There is no `/task` quick-add.
4. **Latency is driven by polling.** Worker polls every 30s. A 3-step workflow takes 90+ seconds minimum from polling alone.
5. **Telegram output is debug-oriented.** `/workflows` outputs run IDs, step names, `paused=`, sync timelines by default. No proactive notifications.
6. **Tests don't catch real behavior.** The Google Calendar "integration" tests have 98 Mock calls — they test nothing about real API behavior or timezone correctness.

## User-Visible Outcome

### When this milestone is complete, the operator can:

- Type `/task need to book flights this week` in Telegram and receive a concise confirmation within seconds, with the task created in the internal system and a Calendar event placed at a reasonable local time
- Type `/task detail car before Wednesday` and either see auto-placement confirmation or an approval request (if the system is uncertain or disruptive) — never silence
- Type `/status` and see pending approvals, recent actions, and the active timezone — no debug internals
- Type `/agenda` and see today's Calendar events at correct local times
- Receive a proactive Telegram notification when any workflow reaches an approval-needed state, without having to poll
- Run `/workflow_start` for a full weekly scheduling request and see it use the same corrected timezone and inference primitives as `/task`

### Entry point / environment

- Entry point: Telegram bot commands (`/task`, `/status`, `/agenda`, `/workflow_start`, `/approve`)
- Environment: docker-compose local dev; real Google Calendar API (staging calendar for tests)
- Live dependencies: Telegram Bot API, Google Calendar API, Postgres

## Completion Class

- Contract complete means: unit and integration tests pass for all new primitives (inference, timezone conversion, approval policy, fast execution path)
- Integration complete means: `/task` → DB task record → Calendar event roundtrip works end-to-end in docker-compose with correct local times
- Operational complete means: live reload works for worker and bot; Datadog logs + APM traces visible for the `/task` path

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- `/task book dentist appointment tomorrow at 2pm` creates a Calendar event at 2pm in OPERATOR_TIMEZONE, not 2pm UTC
- A past-event write attempt is rejected with a clear message
- One `/task` auto-places silently (high confidence, low disruption); one `/task` triggers an approval request (ambiguous/disruptive)
- `/workflow_start` for a weekly scheduling brief uses the same timezone and inference primitives as `/task` — no legacy scheduling logic remains on the weekly path
- `/status` shows pending approvals and active timezone; no run IDs or step names in default output
- E2E test asserts a real Calendar event has the correct start time in operator local timezone, cleans up deterministically, and fails fast if `HELM_CALENDAR_TEST_ID` is missing or "primary"

## Risks and Unknowns

- **LLM inference latency for `/task`** — OpenAI call adds round-trip latency. Mitigation: return immediate "task received" ack, run inference + scheduling async, push result when ready.
- **`_run_calendar_agent` refactor scope** — 435-line file interleaves slot calculation, title parsing, duration inference, and serialization. Extracting shared primitives requires careful surgery to avoid regressions in weekly workflow.
- **Immediate execution architecture** — Running orchestration steps inline from the Telegram bot process. If the bot crashes mid-step, the step may be orphaned. Mitigation: step state is persisted in DB; polling worker recovers orphaned runnable steps.
- **Proactive notification delivery** — `TelegramDigestDeliveryService` uses `asyncio.run()` which can conflict with the bot's existing event loop. Needs careful integration.
- **Datadog setup complexity** — Keep it additive: structured logs work without the agent; APM is best-effort for M004.

## Existing Codebase / Prior Art

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — Contains `_run_task_agent`, `_run_calendar_agent`, `_candidate_slots`, `_parse_slot_from_title`. This is where the timezone and hardcoded-date bugs live. 435 lines. Key refactor target for S02.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` — 2026-line step runner. Manages run state, specialist dispatch, approval checkpoints, sync records. Not to be rewritten; shared primitives plug in here.
- `packages/connectors/src/helm_connectors/google_calendar.py` — `GoogleCalendarAdapter`. RFC3339 formatting is correct. Receives datetimes from upstream — timezone fix is upstream in the scheduling logic, not here.
- `packages/llm/src/helm_llm/client.py` — `LLMClient` wraps OpenAI. Has `summarize()` only. Needs a structured inference method for task semantic extraction (S01).
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` — 366 lines. `_format_run` is the source of debug output verbosity. `start()` is the existing `/workflow_start` handler. New commands go alongside this.
- `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` — `TelegramDigestDeliveryService.deliver()` is the existing proactive push path. Pattern for approval notifications.
- `packages/orchestration/src/helm_orchestration/schemas.py` — `WeeklyTaskRequest`, `WeeklySchedulingRequest`, `TaskAgentInput`, `CalendarAgentInput`, `ScheduleBlock`. Key schemas for the scheduling path.
- `tests/integration/test_google_calendar_adapter_real_api.py` — 98 Mock calls. Misnamed — not a real integration test. To be reclassified and replaced with real E2E coverage in S05.

## Implementation Decisions

- **`/task` storage model:** Task quick-add stores as a workflow artifact for M004 (reuses existing machinery). Dedicated `tasks` table deferred to M005.
- **Approval notification delivery:** Trigger from orchestration step via a registered callback/hook in the bot process. Keep it simple for M004 — no separate notification worker.
- **OPERATOR_TIMEZONE:** Required env var. Fail fast at scheduling time if missing or invalid. Validate against `zoneinfo` IANA database. All local time interpretation happens in this timezone; UTC conversion only at storage/API boundaries.
- **Immediate execution:** Run orchestration steps inline from Telegram handler after persisting the run to DB. Worker polling remains as background recovery for any runnable steps not yet picked up.
- **Shared scheduling primitives location:** Extract to `packages/orchestration/src/helm_orchestration/scheduling.py` (new file). Import from both the worker job handlers and the new `/task` handler.
- **Weekly scheduling request parsing:** `parse_weekly_scheduling_request` stays in `apps/api` for M004 to avoid migration risk; move to shared package is a follow-up.
- **Test layer enforcement:** `tests/unit/` — no DB, no network. `tests/integration/` — in-memory SQLite or test Postgres, no external API. `tests/e2e/` — real APIs, requires `HELM_E2E=true` and `HELM_CALENDAR_TEST_ID` env vars. E2E tests skip (not fail) if env vars absent, but fail explicitly if `HELM_CALENDAR_TEST_ID=primary`.

## Agent's Discretion

- Specific LLM prompt design for task semantic inference
- Whether to use structured outputs (JSON mode) or parse natural language from LLM for inference
- Exact conditional approval scoring implementation (rule-based threshold vs LLM confidence score)
- Specific Datadog library choice (`ddtrace` vs log forwarding via DD agent)
- Whether live reload uses `watchfiles` CLI wrapper or `python -m watchfiles`

## Deferred Ideas

- Dedicated `tasks` table with full lifecycle (M005)
- Bidirectional sync, external edit detection (M005)
- Recurring events (M005)
- Ambient natural-message intent detection (explicitly out of scope)
- `/task` inline keyboard buttons for approve/reject (consider for M005)
