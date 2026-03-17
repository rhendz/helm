# Requirements

## Active

### R100 — `/task` quick-add command with immediate task creation
- Class: primary-user-loop
- Status: active
- Description: `/task <natural language>` creates a task record in the internal system immediately (before calendar placement), infers semantics, attempts placement, and notifies the operator when done.
- Why it matters: The core operator loop starts here. Without a low-friction task entry path, Helm cannot be used reliably day-to-day.
- Source: user
- Primary owning slice: M004/S01
- Supporting slices: M004/S03, M004/S04
- Validation: unmapped
- Notes: Task record must be persisted before placement/sync begins. `/task` is a new fast path, not a replacement for the weekly scheduling workflow.

### R101 — LLM-based task semantic inference
- Class: core-capability
- Status: active
- Description: Helm infers urgency, priority, and sizing (estimated time/effort) from natural language task input. Examples: "need to book flights this week" → medium urgency, medium priority, ~30min; "detail car before Wednesday" → high urgency, low priority, ~2h.
- Why it matters: Without inference, tasks are undifferentiated and unschedulable. The operator should not have to specify these fields manually.
- Source: user
- Primary owning slice: M004/S01
- Supporting slices: M004/S02
- Validation: unmapped
- Notes: Inference runs via LLM (OpenAI). Output feeds into both `/task` and weekly scheduling paths. Shared primitive.

### R102 — OPERATOR_TIMEZONE as required config, fail-fast on missing/invalid
- Class: constraint
- Status: active
- Description: All scheduling behavior reads operator local time from OPERATOR_TIMEZONE env var (IANA format, e.g. America/Los_Angeles). If missing or invalid, Helm refuses to schedule and surfaces a clear error. Active timezone is inspectable in `/status` or `/agenda` output.
- Why it matters: The root cause of the calendar correctness bug. Without an explicit timezone source of truth, scheduling is unreliable by design.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: M004/S04
- Validation: unmapped
- Notes: Replaces the hardcoded UTC base in `_candidate_slots`. Must be visible to operator in status output.

### R103 — Correct local↔UTC conversion throughout scheduling path
- Class: core-capability
- Status: active
- Description: When operator says "Monday 10am", Helm interprets that as 10am in OPERATOR_TIMEZONE, converts to UTC for storage, and sends RFC3339 with correct offset to Google Calendar. The event appears at 10am in the operator's calendar, not at some UTC-equivalent local time.
- Why it matters: The immediate bug. "Monday 10am" is currently written as UTC 10am, landing at 3am PDT.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: M004/S05
- Validation: unmapped
- Notes: Fix spans `_parse_slot_from_title`, `_candidate_slots`, and the ScheduleBlock serialization. Verified by E2E test asserting actual event start time in Calendar.

### R104 — Past-event guard on all calendar write paths
- Class: quality-attribute
- Status: active
- Description: Helm refuses to schedule a Calendar event in the past (relative to now in OPERATOR_TIMEZONE) unless the operator explicitly acknowledges it. Applies to both `/task` and weekly scheduling paths.
- Why it matters: Scheduling "Monday" the day after Monday silently creates a past event. This is unacceptable for a scheduling assistant.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: none
- Validation: unmapped
- Notes: Guard runs at calendar write time, not just at proposal time.

### R105 — Dynamic week calculation replacing hardcoded date
- Class: core-capability
- Status: active
- Description: `_candidate_slots` and related scheduling logic compute the reference week dynamically from the current date in OPERATOR_TIMEZONE, not from the hardcoded `datetime(2026, 3, 16, 9, tzinfo=UTC)`.
- Why it matters: The hardcoded date means the scheduler is already wrong and gets more wrong every week that passes.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: none
- Validation: unmapped
- Notes: Part of the shared scheduling primitives refactor.

### R106 — Immediate execution for operator-triggered workflows; polling as background-only
- Class: operability
- Status: active
- Description: `/task`, `/approve`, and other operator-triggered actions execute immediately (within seconds) without waiting for the 30s polling cycle. Worker polling is retained as a background recovery/fallback mechanism only, not the primary execution driver for operator actions.
- Why it matters: 2–3 minute latency for a simple task add is unacceptable for a tool the operator uses daily.
- Source: user
- Primary owning slice: M004/S03
- Supporting slices: M004/S01
- Validation: unmapped
- Notes: Implementation: trigger step execution inline from the Telegram handler (or via a minimal fast queue) after state is persisted. Polling remains for steps that were left runnable but not yet picked up.

### R107 — Conditional approval policy: auto-place on high confidence + low disruption; ask otherwise
- Class: core-capability
- Status: active
- Description: Helm auto-places a task and notifies the operator when: confidence is high AND the block is ≤2h AND placement does not shift or conflict with another event. Helm asks for approval when: confidence is low, sizing is ambiguous, block >2h, placement would displace or conflict with another event, or the scheduling interpretation is unclear.
- Why it matters: Operator said "approval only when needed." Defining the policy explicitly prevents both over-asking (annoying) and silent bad placements (untrustworthy).
- Source: user
- Primary owning slice: M004/S01
- Supporting slices: M004/S04
- Validation: unmapped
- Notes: Policy is a shared primitive used by both `/task` and weekly scheduling.

### R108 — Proactive approval notifications via Telegram push
- Class: operability
- Status: active
- Description: When any workflow reaches an approval-needed state, Helm pushes a Telegram notification to the operator immediately. Operator does not need to poll `/status` or `/workflows` to discover pending approvals.
- Why it matters: The current system requires the operator to manually check for pending approvals, which defeats the purpose of an assistant.
- Source: user
- Primary owning slice: M004/S04
- Supporting slices: M004/S03
- Validation: unmapped
- Notes: Uses existing `TelegramDigestDeliveryService.deliver()` pattern or equivalent bot.send_message. Fires when orchestration records an approval checkpoint.

### R109 — `/status` command: pending approvals, recent actions, current state, active timezone
- Class: operability
- Status: active
- Description: `/status` returns a concise operator-facing view: pending approvals (with action commands), recent completions (last 3–5), any active workflows, and the configured OPERATOR_TIMEZONE. No debug internals by default.
- Why it matters: Replaces the current `/workflows` command which dumps run IDs, step names, paused states, and sync timelines by default.
- Source: user
- Primary owning slice: M004/S04
- Supporting slices: none
- Validation: unmapped
- Notes: Active timezone must be visible here. `/workflows` can remain for power-user detail access.

### R110 — `/agenda` command: today's calendar from Google Calendar
- Class: operability
- Status: active
- Description: `/agenda` fetches today's events from the operator's Google Calendar and presents them concisely: event title, time in OPERATOR_TIMEZONE, duration. No internal IDs or sync metadata by default.
- Why it matters: Closes the loop — operator can verify what Helm scheduled without opening the Calendar app.
- Source: user
- Primary owning slice: M004/S04
- Supporting slices: none
- Validation: unmapped
- Notes: Reads from Google Calendar API using existing OAuth credentials.

### R111 — Telegram output is concise by default; debug/detail available on explicit request
- Class: operability
- Status: active
- Description: Default Telegram output for all commands shows operator-relevant information only: what changed, what needs attention, what actions are available. Internal IDs, step names, sync timelines, paused states, and artifact IDs are hidden unless the operator explicitly requests detail.
- Why it matters: Current output overloads the operator with internal state, making Helm feel like a debugging tool rather than an assistant.
- Source: user
- Primary owning slice: M004/S04
- Supporting slices: none
- Validation: unmapped
- Notes: `/workflows` and similar commands remain for explicit detail access. Default formatting is overhauled.

### R112 — `/task` and weekly scheduling share core scheduling primitives
- Class: core-capability
- Status: active
- Description: Timezone conversion, task inference, conditional approval policy, past-event guard, and calendar write rules are implemented once as shared primitives and used by both the `/task` fast path and the weekly scheduling workflow. No duplicated scheduling logic between the two entry points.
- Why it matters: If the two paths diverge, fixes in one place won't carry to the other. The weekly workflow must be updated to use the corrected primitives, not left running legacy logic.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: M004/S01, M004/S06
- Validation: unmapped
- Notes: Weekly scheduling workflow remains a supported separate entry point. The refactor is about shared primitives, not merging the workflows.

### R113 — Strict test layer boundaries: unit (pure), integration (DB, no external), E2E (real staging calendar)
- Class: quality-attribute
- Status: active
- Description: Unit tests exercise pure functions with no DB or network. Integration tests use in-memory/test Postgres with no external API calls. E2E tests are explicitly marked and call the real Google Calendar API against a staging calendar ID. No mixing of layers within a test file.
- Why it matters: The current "integration" tests for Google Calendar are fully mocked (98 Mock calls) — they provide no signal about real API behavior. This is why the timezone bug went undetected.
- Source: user
- Primary owning slice: M004/S05
- Supporting slices: none
- Validation: unmapped
- Notes: E2E tests run in CI only when `HELM_CALENDAR_TEST_ID` and `HELM_E2E=true` are set.

### R114 — E2E tests assert real datetime/timezone correctness; fail-fast on unsafe calendar target
- Class: quality-attribute
- Status: active
- Description: E2E tests write a real event to the staging calendar, read it back, and assert the start/end times match the expected local times in OPERATOR_TIMEZONE (not just that an event was written). Tests fail fast if `HELM_CALENDAR_TEST_ID` is missing, empty, or equals "primary".
- Why it matters: The timezone bug cannot be caught by mocked tests. Real calendar assertions are the only trustworthy signal.
- Source: user
- Primary owning slice: M004/S05
- Supporting slices: none
- Validation: unmapped
- Notes: Tests clean up created events deterministically (delete in teardown). Never default to primary calendar.

### R115 — Weekly scheduling workflow remains a supported entry point using shared primitives
- Class: continuity
- Status: active
- Description: The weekly scheduling workflow (`/workflow_start`) continues to work end-to-end in M004. It is updated to use the same shared scheduling primitives (timezone, inference, approval policy, calendar write rules) as `/task`. No duplicated legacy scheduling logic remains.
- Why it matters: Operator confirmed the weekly workflow should survive M004. Existing integrations (API + worker + Telegram) must not regress.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: M004/S06
- Validation: unmapped
- Notes: Existing integration tests for weekly scheduling must remain passing.

### R116 — Live reload for worker and telegram-bot in docker-compose
- Class: operability
- Status: active
- Description: Code changes to worker and telegram-bot source files are picked up without a full docker-compose restart. API already has `--reload`; worker and bot need equivalent watchfiles-based reload.
- Why it matters: Current dev loop requires full restart for every change, adding friction to iteration.
- Source: user
- Primary owning slice: M004/S06
- Supporting slices: none
- Validation: unmapped
- Notes: Use `watchfiles` or `python -m watchfiles`. Add to pyproject.toml dev deps if not present.

### R117 — Datadog structured logs + APM on key request/workflow paths
- Class: operability
- Status: active
- Description: Helm services emit structured JSON logs compatible with Datadog ingestion. APM traces cover the `/task` request path from Telegram command through inference, scheduling, and calendar write. Basic service health is observable via Datadog.
- Why it matters: Currently there is no external observability — diagnosing where latency happens or where workflows stall requires direct log access.
- Source: user
- Primary owning slice: M004/S06
- Supporting slices: none
- Validation: unmapped
- Notes: Use `ddtrace` or Datadog agent log forwarding. Scope: logs + APM on key paths. No custom metrics required for M004.

### R118 — Code cleanup: remove placeholder scheduling behavior, dead legacy logic
- Class: quality-attribute
- Status: active
- Description: Remove or replace placeholder scheduling behavior (hardcoded base date, stub task agent logic, duplicated scheduling paths). Simplify the scheduling path where complexity is not earning its keep. Remove tests that test stubs rather than real behavior.
- Why it matters: Technical debt in the scheduling path is directly causing reliability failures. Leaving it in place while building on top makes the foundation worse.
- Source: user
- Primary owning slice: M004/S06
- Supporting slices: M004/S02
- Validation: unmapped
- Notes: Cleanup should follow the shared primitives refactor in S02 — don't clean up code that's about to be replaced.

## Validated

(All prior M001–M003 requirements remain validated. See M001–M003 summaries for details.)

- REQ-DURABLE-PERSISTENCE — validated M001/S01
- REQ-SPECIALIST-DISPATCH — validated M001/S02
- REQ-APPROVAL-CHECKPOINTS — validated M001/S02
- REQ-ADAPTER-SYNC — validated M001/S03
- REQ-REPRESENTATIVE-WORKFLOW — validated M001/S04
- REQ-OPERATOR-SURFACES — validated M001/S04
- R002 — validated M002/S02
- R003 — validated M002/S03
- R005 — validated M002/S02
- R006 — validated M003/S01
- R010 — validated M003/S01
- R011 — validated M003/S02
- R012 — validated M003/S03
- R013 — validated M003/S05

## Deferred

### R200 — Bidirectional calendar sync (external edit detection → internal reconciliation)
- Class: integration
- Status: deferred
- Description: When operator edits an event in Calendar directly, Helm detects the change and reconciles internal state. Conflict detection and auto-resolution or operator notification.
- Why it matters: Full bidirectional sync requires a stable, correct foundation to build on.
- Source: user
- Primary owning slice: M005
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred to M005. Drift detection infrastructure from M003 provides a starting point.

### R201 — Recurring event support
- Class: core-capability
- Status: deferred
- Description: Recurring events can be created via Helm and propagate correctly into Google Calendar. Internal scheduling model supports recurrence.
- Why it matters: A scheduling assistant without recurrence is incomplete.
- Source: user
- Primary owning slice: M005
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred to M005.

### R202 — Reactive webhook-based calendar change detection
- Class: integration
- Status: deferred
- Description: Replace polling-based external change detection with Google Calendar push notifications (webhooks) where viable.
- Why it matters: Polling wastes API quota and adds latency. Webhooks are the right long-term architecture.
- Source: user
- Primary owning slice: M005
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred to M005. Polling remains as fallback even with webhooks.

### R020 — Additional workflows beyond scheduling
- Class: primary-user-loop
- Status: deferred
- Description: Running additional domain workflows (email, study, etc.) on the same kernel contract.
- Source: execution
- Primary owning slice: none
- Validation: unmapped

## Out of Scope

### R300 — Temporal migration
- Class: anti-feature
- Status: out-of-scope
- Description: Replacing the custom DB-backed step runner with Temporal.
- Why it matters: Prevents scope creep. Current issues are implementation quality problems, not architecture problems.
- Source: user
- Primary owning slice: none
- Validation: n/a

### R301 — Ambient natural-message intent detection
- Class: anti-feature
- Status: out-of-scope
- Description: Detecting intent from plain Telegram messages without a slash command.
- Why it matters: Requires the system to be trustworthy first. M004 uses explicit commands.
- Source: user
- Primary owning slice: none
- Validation: n/a

### R302 — Web dashboard / non-Telegram UI
- Class: anti-feature
- Status: out-of-scope
- Description: Building a primary web dashboard or UI.
- Source: user
- Primary owning slice: none
- Validation: n/a

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|----|-------|--------|---------------|------------|-------|
| R100 | primary-user-loop | active | M004/S01 | M004/S03, S04 | unmapped |
| R101 | core-capability | active | M004/S01 | M004/S02 | unmapped |
| R102 | constraint | active | M004/S02 | M004/S04 | unmapped |
| R103 | core-capability | active | M004/S02 | M004/S05 | unmapped |
| R104 | quality-attribute | active | M004/S02 | none | unmapped |
| R105 | core-capability | active | M004/S02 | none | unmapped |
| R106 | operability | active | M004/S03 | M004/S01 | unmapped |
| R107 | core-capability | active | M004/S01 | M004/S04 | unmapped |
| R108 | operability | active | M004/S04 | M004/S03 | unmapped |
| R109 | operability | active | M004/S04 | none | unmapped |
| R110 | operability | active | M004/S04 | none | unmapped |
| R111 | operability | active | M004/S04 | none | unmapped |
| R112 | core-capability | active | M004/S02 | S01, S06 | unmapped |
| R113 | quality-attribute | active | M004/S05 | none | unmapped |
| R114 | quality-attribute | active | M004/S05 | none | unmapped |
| R115 | continuity | active | M004/S02 | M004/S06 | unmapped |
| R116 | operability | active | M004/S06 | none | unmapped |
| R117 | operability | active | M004/S06 | none | unmapped |
| R118 | quality-attribute | active | M004/S06 | M004/S02 | unmapped |
| R200 | integration | deferred | M005 | none | unmapped |
| R201 | core-capability | deferred | M005 | none | unmapped |
| R202 | integration | deferred | M005 | none | unmapped |
| R020 | primary-user-loop | deferred | none | none | unmapped |
| R300 | anti-feature | out-of-scope | none | none | n/a |
| R301 | anti-feature | out-of-scope | none | none | n/a |
| R302 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 19 (R100–R118)
- Mapped to slices: 19
- Validated: 0 (M004 not started)
- Unmapped active requirements: 0
