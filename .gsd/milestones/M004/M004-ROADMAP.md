# M004: Foundation Repair

**Vision:** Restore trust in the core Helm operator loop. The operator sends `/task` or `/workflow_start` via Telegram, Helm infers task semantics, schedules at the correct local time, writes to Calendar, and notifies when done — with low friction, correct behavior, and proactive communication rather than requiring the operator to poll for status.

## Success Criteria

- `/task <natural language>` creates a task in the internal system immediately and places a Calendar event at the correct operator-local time
- Weekly scheduling workflow continues to work end-to-end as a separate entry point using the same shared scheduling primitives
- All Calendar events land at the correct local time (not UTC-interpreted local time)
- Past-event writes are rejected with a clear message
- Conditional approval: one high-confidence low-disruption task auto-places; one ambiguous/disruptive task requests approval
- `/status` shows pending approvals, recent actions, and active timezone — no debug internals by default
- `/agenda` shows today's Calendar events in operator local time
- Proactive Telegram notifications fire when approval is needed — no polling required
- E2E tests run against staging calendar with real datetime correctness assertions
- Worker and telegram-bot live-reload on code changes
- Datadog logs and APM traces cover the `/task` path

## Key Risks / Unknowns

- LLM inference latency may make `/task` feel slow — needs async ack + push-on-complete pattern
- Extracting shared primitives from the 435-line `workflow_runs.py` requires careful surgery to avoid weekly workflow regressions
- Inline execution from Telegram handler creates a crash-recovery concern — mitigated by DB-persisted step state and background polling recovery
- `asyncio.run()` in `TelegramDigestDeliveryService` may conflict with bot event loop — needs careful integration for proactive notifications

## Proof Strategy

- LLM inference latency → retire in S01 by proving `/task` returns an ack within 2s and pushes result asynchronously
- Timezone correctness → retire in S02 by E2E test asserting real Calendar event start time matches operator local time
- Scheduling primitive regression → retire in S02 by running full weekly scheduling integration test suite after refactor
- Inline execution crash safety → retire in S03 by proving worker polling recovers an orphaned runnable step

## Verification Classes

- Contract verification: pytest unit tests for inference, timezone conversion, approval policy, scheduling primitives; integration tests for workflow step execution and DB state
- Integration verification: docker-compose end-to-end `/task` flow creating a real Calendar event at correct local time
- Operational verification: live reload confirmed by editing a source file and seeing the change reflected without restart; Datadog log stream shows structured entries for a `/task` call
- UAT / human verification: operator runs `/task` in real Telegram, checks Calendar, verifies correct time; runs `/status`, sees active timezone

## Milestone Definition of Done

This milestone is complete only when all are true:

- `/task` quick-add creates a task record immediately, infers semantics via LLM, and places a Calendar event (or requests approval) — all completing within seconds
- Weekly scheduling workflow (`/workflow_start`) works end-to-end and uses shared scheduling primitives — no legacy slot calculation, hardcoded dates, or stub task agent logic remains
- OPERATOR_TIMEZONE is required config; scheduling fails fast if absent; timezone is visible in `/status` output
- All Calendar write paths enforce the past-event guard
- Proactive Telegram notifications push when a workflow reaches approval-needed state
- `/status` and `/agenda` commands are clean and operator-facing; debug detail requires explicit request
- E2E test suite writes to staging calendar, asserts correct local times, cleans up, and fails fast on unsafe calendar config
- Worker and telegram-bot live-reload on source file changes
- Datadog structured logs and APM traces cover the `/task` path end-to-end
- Hardcoded scheduling stubs and duplicated scheduling logic removed
- All prior M001–M003 integration tests still pass (no regressions)

## Requirement Coverage

- Covers: R100, R101, R102, R103, R104, R105, R106, R107, R108, R109, R110, R111, R112, R113, R114, R115, R116, R117, R118
- Partially covers: none
- Leaves for later: R200, R201, R202 (M005)
- Orphan risks: none

## Slices

- [x] **S01: Task inference engine and `/task` quick-add** `risk:high` `depends:[]`
  > After this: `/task need to book flights this week` creates a task in the DB with inferred urgency/priority/sizing and replies with a concise confirmation — task record persisted immediately, calendar placement flows async

- [x] **S02: Timezone correctness and shared scheduling primitives** `risk:high` `depends:[S01]`
  > After this: weekly scheduling request schedules "Monday 10am" at the correct local time in Calendar; past-event guard rejects stale writes; `/task` and weekly workflow share the same timezone/inference/approval/calendar-write primitives — no duplicated legacy logic

- [x] **S03: Immediate execution path for operator actions** `risk:medium` `depends:[S01,S02]`
  > After this: `/task` and `/approve` complete within seconds using corrected scheduling behavior; polling loop retained only for background recovery of orphaned runnable steps

- [x] **S04: Telegram UX overhaul and proactive notifications** `risk:medium` `depends:[S01,S02,S03]`
  > After this: `/status` shows pending approvals, recent actions, and active OPERATOR_TIMEZONE; `/agenda` shows today's Calendar events in local time; Helm pushes an approval notification without being polled; one `/task` auto-places (high confidence, low disruption) and one triggers an approval request (ambiguous/disruptive); default output is concise and operator-facing

- [x] **S05: Strict test boundaries and real E2E calendar coverage** `risk:high` `depends:[S02,S03]`
  > After this: E2E test suite writes to staging calendar, reads back events, asserts correct local times in OPERATOR_TIMEZONE, cleans up deterministically; fails fast if `HELM_CALENDAR_TEST_ID` is missing or "primary"; unit/integration/E2E layers are strictly separated with no mocks leaking across boundaries

- [x] **S06: Dev experience, observability, and cleanup** `risk:low` `depends:[S01,S05]`
  > After this: `milestone/M004` branch (S01–S04: LLM inference, `/task` handler, approval policy, proactive notifications, `/status`, `/agenda`) merged into `main` and verified against the 436-test suite; worker and telegram-bot live-reload on source file changes; Datadog logs and APM traces visible for a `/task` flow; hardcoded scheduling stubs and duplicated legacy scheduling logic removed from codebase. **Branch merge is the first step — without it, M004 is not deployable.**

## Boundary Map

### S01 → S02

Produces:
- `packages/llm/src/helm_llm/inference.py` — `infer_task_semantics(text: str) -> TaskSemantics` (urgency, priority, sizing_minutes, confidence)
- `packages/orchestration/src/helm_orchestration/scheduling.py` (stub) — `ApprovalPolicy` interface and `ConditionalApprovalPolicy` rule set (block >2h, low confidence, conflicts → ask; otherwise auto-place)
- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` — `/task` handler: persists task workflow run, triggers async execution, replies with ack
- `WeeklyTaskRequest` extended with `urgency` and `confidence` fields in `packages/orchestration/src/helm_orchestration/schemas.py`

Consumes: nothing (first slice)

### S01 → S03

Produces:
- Task workflow run creation path in Telegram handler (DB-persisted run before async execution)
- `TaskSemantics` schema for downstream consumption

Consumes: nothing (first slice)

### S02 → S03

Produces:
- `packages/orchestration/src/helm_orchestration/scheduling.py` — complete shared primitives: `compute_reference_week(timezone: ZoneInfo) -> datetime`, `parse_local_slot(title: str, week_start: datetime, timezone: ZoneInfo) -> datetime | None`, `to_utc(local_dt: datetime, timezone: ZoneInfo) -> datetime`, `past_event_guard(dt: datetime, timezone: ZoneInfo) -> None`, `ConditionalApprovalPolicy.evaluate(block: ScheduleBlock, confidence: float) -> ApprovalDecision`
- `_candidate_slots`, `_parse_slot_from_title`, `_run_task_agent`, `_run_calendar_agent` in `workflow_runs.py` updated to delegate to shared primitives
- `OPERATOR_TIMEZONE` config in `packages/runtime/src/helm_runtime/config.py`

Consumes from S01:
- `TaskSemantics` schema
- `infer_task_semantics()` for use in shared task normalization

### S02 → S05

Produces:
- All scheduling correctness guarantees (timezone conversion, past-event guard, dynamic week)
- `OPERATOR_TIMEZONE` config interface

Consumes from S01:
- `infer_task_semantics()` (for integration test coverage of the full path)

### S03 → S04

Produces:
- Direct execution path: `execute_task_workflow_inline(run_id: int, session: Session)` callable from Telegram handler
- Approval notification hook: `notify_approval_needed(run_id: int, proposal: ScheduleBlock)` — fires proactive push when approval checkpoint is reached
- Polling loop reduced to background-only recovery

Consumes from S01:
- `/task` handler structure (async ack pattern)

Consumes from S02:
- Shared scheduling primitives (all step execution uses corrected timezone/approval logic)

### S03 → S05

Produces:
- Execution path unit testable in isolation (injectable execution function)

### S04 → S05

Produces:
- `/status` command output format (for E2E assertion against real state)
- `/agenda` command reading from real Calendar (for E2E verification of placed events)

Consumes from S01:
- Task workflow run state format
Consumes from S02:
- OPERATOR_TIMEZONE config (visible in `/status`)
Consumes from S03:
- Proactive notification hook
- Direct execution result format

### S06 → (all)

Produces:
- Merged codebase: `milestone/M004` (S01–S04 implementation) unified with `main` (S05 test infrastructure + ported primitives); conflicts in `scheduling.py`, `schemas.py`, `workflow_status_service.py` resolved by taking the more complete S01–S04 version, verified against 436 tests
- Cleaned codebase: no hardcoded dates, no duplicated scheduling logic, no stub task agent
- Live reload for worker and bot
- Datadog instrumentation on `/task` path

Consumes from S01:
- New modules to instrument (inference, task handler)

Consumes from S05:
- 436-test baseline to verify post-merge correctness
