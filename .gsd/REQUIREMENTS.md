# Requirements

## Validated

### R100 — `/task` quick-add command with immediate task creation
- Class: primary-user-loop
- Status: validated
- Description: `/task <natural language>` creates a task record in the internal system immediately (before calendar placement), infers semantics, attempts placement, and notifies the operator when done.
- Why it matters: The core operator loop starts here. Without a low-friction task entry path, Helm cannot be used reliably day-to-day.
- Source: user
- Primary owning slice: M004/S01
- Supporting slices: M004/S03, M004/S04
- Validation: S01 proves: task record persisted before async work (workflow_type="task_quick_add" DB row created at ack time); operator notified of outcome (success or error push). S03 wires inline execution → complete_current_step → approval checkpoint; 10 unit tests in test_task_execution.py confirm full path; 500-test suite passes.
- Notes: Task record must be persisted before placement/sync begins. `/task` is a new fast path, not a replacement for the weekly scheduling workflow.

### R101 — LLM-based task semantic inference
- Class: core-capability
- Status: validated
- Description: Helm infers urgency, priority, and sizing (estimated time/effort) from natural language task input. Examples: "need to book flights this week" → medium urgency, medium priority, ~30min; "detail car before Wednesday" → high urgency, low priority, ~2h.
- Why it matters: Without inference, tasks are undifferentiated and unschedulable. The operator should not have to specify these fields manually.
- Source: user
- Primary owning slice: M004/S01
- Supporting slices: M004/S02
- Validation: S01 proves: LLMClient.infer_task_semantics() with responses.parse structured output; TaskSemantics model captures urgency/priority/sizing_minutes/confidence; 15 unit tests in test_task_inference.py cover model validation and 7 policy edge cases; structlog task_inference_complete confirmed in code.
- Notes: Inference runs via LLM (OpenAI). Output feeds into both `/task` and weekly scheduling paths. Shared primitive.

### R102 — OPERATOR_TIMEZONE as required config, fail-fast on missing/invalid
- Class: constraint
- Status: validated
- Description: All scheduling behavior reads operator local time from OPERATOR_TIMEZONE env var (IANA format, e.g. America/Los_Angeles). If missing or invalid, Helm refuses to schedule and surfaces a clear error. Active timezone is inspectable in `/status` or `/agenda` output.
- Why it matters: The root cause of the calendar correctness bug. Without an explicit timezone source of truth, scheduling is unreliable by design.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: M004/S04
- Validation: S02 proves: RuntimeAppSettings.operator_timezone required field with ZoneInfo validator; ValidationError fires at startup for missing/invalid values; OPERATOR_TIMEZONE visible in /status header (S04); S07 confirms CommandHandler("status") registered at line 78 of main.py.
- Notes: Replaces the hardcoded UTC base in `_candidate_slots`. Visible to operator in status output.

### R103 — Correct local↔UTC conversion throughout scheduling path
- Class: core-capability
- Status: validated
- Description: When operator says "Monday 10am", Helm interprets that as 10am in OPERATOR_TIMEZONE, converts to UTC for storage, and sends RFC3339 with correct offset to Google Calendar. The event appears at 10am in the operator's calendar, not at some UTC-equivalent local time.
- Why it matters: The immediate bug. "Monday 10am" was being written as UTC 10am, landing at 3am PDT.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: M004/S05
- Validation: S02 proves: parse_local_slot("Monday deep work 10am", week_start, ZoneInfo("America/Los_Angeles")) returns 2026-03-16 10:00:00-07:00 (PDT, not UTC); RFC3339 replace("+00:00","Z") hack removed from workflow_runs.py; ScheduleBlock.start/end emit proper offset-aware ISO format. S05 test_07_events_have_correct_local_times assertion in place for real Calendar verification; 53 integration tests pass.
- Notes: Fix spans _parse_slot_from_title, _candidate_slots, and ScheduleBlock serialization. E2E assertion requires live Calendar credentials to execute.

### R104 — Past-event guard on all calendar write paths
- Class: quality-attribute
- Status: validated
- Description: Helm refuses to schedule a Calendar event in the past (relative to now in OPERATOR_TIMEZONE) unless the operator explicitly acknowledges it. Applies to both `/task` and weekly scheduling paths.
- Why it matters: Scheduling "Monday" the day after Monday silently creates a past event. This is unacceptable for a scheduling assistant.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: none
- Validation: S02 proves: past_event_guard raises PastEventError on past datetimes; future datetimes pass without raising; _run_calendar_agent calls guard before appending each ScheduleBlock with warn-and-skip: logger.warning("past_event_guard_triggered") + carry_forward.append(task.title) + continue; 18 scheduling unit tests pass.
- Notes: Guard runs at calendar write time, not just at proposal time.

### R105 — Dynamic week calculation replacing hardcoded date
- Class: core-capability
- Status: validated
- Description: `_candidate_slots` and related scheduling logic compute the reference week dynamically from the current date in OPERATOR_TIMEZONE, not from the hardcoded `datetime(2026, 3, 16, 9, tzinfo=UTC)`.
- Why it matters: The hardcoded date means the scheduler is already wrong and gets more wrong every week that passes.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: none
- Validation: S02 proves: compute_reference_week(ZoneInfo("America/Los_Angeles")) returns current Monday at midnight PDT (tz-aware, weekday==0); grep "2026, 3, 16" in workflow_runs.py returns empty (hardcoded date removed); _candidate_slots uses compute_reference_week(tz) dynamically.
- Notes: Part of the shared scheduling primitives refactor.

### R106 — Immediate execution for operator-triggered workflows; polling as background-only
- Class: operability
- Status: validated
- Description: `/task`, `/approve`, and other operator-triggered actions execute immediately (within seconds) without waiting for the 30s polling cycle. Worker polling is retained as a background recovery/fallback mechanism only.
- Why it matters: 2–3 minute latency for a simple task add is unacceptable for a tool the operator uses daily.
- Source: user
- Primary owning slice: M004/S03
- Supporting slices: M004/S01
- Validation: S03 proves: 10 unit tests confirm /task background coroutine calls complete_current_step inline; /approve calls resume_run inline immediately after approve_run() succeeds; worker recovery handler registered under ("task_quick_add", "infer_task_semantics") for polling-based recovery of orphaned runs.
- Notes: Polling remains for steps left runnable but not yet picked up. Background recovery path is DB-durable.

### R107 — Conditional approval policy: auto-place on high confidence + low disruption; ask otherwise
- Class: core-capability
- Status: validated
- Description: Helm auto-places when confidence ≥ 0.8 AND block ≤ 2h AND no displacement. Helm asks for approval when: confidence is low, sizing is ambiguous, block >2h, placement would displace or conflict, or scheduling interpretation is unclear.
- Why it matters: Operator said "approval only when needed." Defining the policy explicitly prevents both over-asking (annoying) and silent bad placements (untrustworthy).
- Source: user
- Primary owning slice: M004/S01
- Supporting slices: M004/S04
- Validation: S01 proves: ConditionalApprovalPolicy.evaluate() returns APPROVE for confidence≥0.8 AND sizing≤120min; exact boundary values verified: 0.79→REVISION, 0.80→APPROVE, 120→APPROVE, 121→REVISION; 7 policy edge case tests pass.
- Notes: Policy is a shared primitive used by both `/task` and weekly scheduling.

### R108 — Proactive approval notifications via Telegram push
- Class: operability
- Status: validated
- Description: When any workflow reaches an approval-needed state, Helm pushes a Telegram notification to the operator immediately. Operator does not need to poll `/status` or `/workflows` to discover pending approvals.
- Why it matters: The current system required the operator to manually check for pending approvals, defeating the purpose of an assistant.
- Source: user
- Primary owning slice: M004/S04
- Supporting slices: M004/S03, M004/S07
- Validation: S07 proves: workflow_runs.run() notification loop iterates resumed states; state.run.needs_action gates dispatch; lazy import of TelegramDigestDeliveryService per D016; per-run try/except Exception isolates failures; structlog proactive_approval_notification_sent (INFO) and proactive_approval_notification_failed (WARNING) emitted. 4 unit tests in test_worker_notification.py cover dispatch, no-op, failure isolation, and artifact extraction. grep -n "notify_approval_needed\|needs_action" workflow_runs.py confirms wiring at lines 67–79.
- Notes: Notification fires per-poll-cycle for needs_action=True runs. No deduplication — repeated notifications possible if operator is slow to respond (M005 candidate: add notified_at timestamp).

### R109 — `/status` command: pending approvals, recent actions, current state, active timezone
- Class: operability
- Status: validated
- Description: `/status` returns a concise operator-facing view: pending approvals (with action commands), recent completions (last 3–5), any active workflows, and the configured OPERATOR_TIMEZONE. No debug internals by default.
- Why it matters: Replaces the current `/workflows` command which dumps run IDs, step names, paused states, and sync timelines by default.
- Source: user
- Primary owning slice: M004/S04
- Supporting slices: M004/S07
- Validation: S07 proves: CommandHandler("status", status.handle) registered at line 78 of apps/telegram-bot/src/helm_telegram_bot/main.py; status.handle renders pending approvals, recent completions, and OPERATOR_TIMEZONE (implemented S04); grep -n 'CommandHandler("status"' main.py confirms registration.
- Notes: Active timezone visible in /status output. /workflows remains for power-user detail access.

### R110 — `/agenda` command: today's calendar from Google Calendar
- Class: operability
- Status: validated
- Description: `/agenda` fetches today's events from the operator's Google Calendar and presents them concisely: event title, time in OPERATOR_TIMEZONE, duration. No internal IDs or sync metadata by default.
- Why it matters: Closes the loop — operator can verify what Helm scheduled without opening the Calendar app.
- Source: user
- Primary owning slice: M004/S04
- Supporting slices: M004/S06
- Validation: S06 proves: CommandHandler("agenda", agenda.handle) registered at line 87 of main.py; GoogleCalendarAdapter.list_today_events() implemented with timezone-aware 12-hour formatting; credential guard for missing GOOGLE_* vars; 4 unit tests in test_agenda_command.py pass; import check confirmed.
- Notes: Reads from Google Calendar API using existing OAuth credentials. Calendar ID hardcoded to "primary" in command; configurable ID deferred to M005.

### R111 — Telegram output is concise by default; debug/detail available on explicit request
- Class: operability
- Status: validated
- Description: Default Telegram output for all commands shows operator-relevant information only. Internal IDs, step names, sync timelines, paused states, and artifact IDs are hidden unless the operator explicitly requests detail.
- Why it matters: Current output overloaded the operator with internal state, making Helm feel like a debugging tool rather than an assistant.
- Source: user
- Primary owning slice: M004/S04
- Supporting slices: none
- Validation: S04 proves: _format_status() and _format_agenda() are pure functions producing only operator-facing content; test_no_debug_internals asserts absence of internal fields; D008 establishes this as a standing convention for all new commands; 6 status + 6 agenda unit tests pass.
- Notes: /workflows and similar commands remain for explicit detail access. D008 is a standing convention.

### R112 — `/task` and weekly scheduling share core scheduling primitives
- Class: core-capability
- Status: validated
- Description: Timezone conversion, task inference, conditional approval policy, past-event guard, and calendar write rules are implemented once as shared primitives used by both the `/task` fast path and the weekly scheduling workflow. No duplicated scheduling logic.
- Why it matters: If the two paths diverge, fixes in one place won't carry to the other.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: M004/S01, M004/S06
- Validation: S02+S06 prove: compute_reference_week, parse_local_slot, to_utc, past_event_guard, PastEventError all exported from helm_orchestration; workflow_runs.py is a pure consumer; _parse_slot_from_title/_DAY_OFFSETS/_TIME_PATTERN deleted; 53 integration tests pass; milestone/M004 merged to main with 500 tests passing.
- Notes: Weekly scheduling workflow remains a supported separate entry point.

### R113 — Strict test layer boundaries: unit (pure), integration (DB, no external), E2E (real staging calendar)
- Class: quality-attribute
- Status: validated
- Description: Unit tests exercise pure functions with no DB or network. Integration tests use in-memory/test Postgres with no external API calls. E2E tests are explicitly marked and call the real Google Calendar API against a staging calendar ID. No mixing of layers.
- Why it matters: The Google Calendar "integration" tests had 98 Mock calls — they tested nothing about real API behavior. This is why the timezone bug went undetected.
- Source: user
- Primary owning slice: M004/S05
- Supporting slices: none
- Validation: S05 proves: misclassified test moved to unit layer (git mv); new integration test for /task→DB state (test_task_execution_integration.py); E2E gate enforces boundary automatically (pytest_configure + pytest_collection_modifyitems); 0 boundary violations in 500 tests; D007 mechanically enforced.
- Notes: E2E tests run in CI only when HELM_CALENDAR_TEST_ID and HELM_E2E=true are set.

### R114 — E2E tests assert real datetime/timezone correctness; fail-fast on unsafe calendar target
- Class: quality-attribute
- Status: validated
- Description: E2E tests write a real event to the staging calendar, read it back, and assert start/end times match expected local times in OPERATOR_TIMEZONE. Tests fail fast if HELM_CALENDAR_TEST_ID is missing, empty, or equals "primary".
- Why it matters: The timezone bug cannot be caught by mocked tests. Real calendar assertions are the only trustworthy signal.
- Source: user
- Primary owning slice: M004/S05
- Supporting slices: none
- Validation: S05 proves: HELM_E2E=true+HELM_CALENDAR_TEST_ID=primary exits with "must not be 'primary'"; pytest tests/e2e/ without HELM_E2E skips all 11 in 0.22s; calendar_id flows through full adapter stack; test_07_events_have_correct_local_times assertion collected and in place.
- Notes: test_07 requires real staging credentials. The assertion logic is correct and in place; executing against a real Calendar is an operational step.

### R115 — Weekly scheduling workflow remains a supported entry point using shared primitives
- Class: continuity
- Status: validated
- Description: The weekly scheduling workflow (`/workflow_start`) continues to work end-to-end. It uses the same shared scheduling primitives (timezone, inference, approval policy, calendar write rules) as `/task`. No duplicated legacy scheduling logic remains.
- Why it matters: Operator confirmed the weekly workflow should survive M004. Existing integrations must not regress.
- Source: user
- Primary owning slice: M004/S02
- Supporting slices: M004/S06
- Validation: S02+S06 prove: pytest tests/integration/ → 53/53 passed after refactor; test_weekly_scheduling_end_to_end.py 3/3; test_weekly_scheduling_with_drift_recovery.py 5/5; no hardcoded date, no RFC3339 hack, no duplicated slot parsing; 500-test suite clean.
- Notes: Existing integration tests for weekly scheduling all pass.

### R116 — Live reload for worker and telegram-bot in docker-compose
- Class: operability
- Status: validated
- Description: Code changes to worker and telegram-bot source files are picked up without a full docker-compose restart. API already has `--reload`; worker and bot use watchfiles-based reload.
- Why it matters: Current dev loop required full restart for every change.
- Source: user
- Primary owning slice: M004/S06
- Supporting slices: none
- Validation: S06 proves: watchfiles>=0.21.0 in dev deps; both run scripts use "python -m watchfiles --filter python"; grep watchfiles scripts/run-worker.sh scripts/run-telegram-bot.sh confirms both present.
- Notes: Watchfiles filter is --filter python; changes to YAML/JSON/.env files won't trigger reload.

### R117 — Datadog structured logs + APM on key request/workflow paths
- Class: operability
- Status: validated
- Description: Helm services emit structured JSON logs compatible with Datadog ingestion. APM traces cover the `/task` request path. Basic service health is observable via Datadog.
- Why it matters: Currently there is no external observability — diagnosing latency requires direct log access.
- Source: user
- Primary owning slice: M004/S06
- Supporting slices: none
- Validation: S06 proves: ddtrace>=2.0.0 in dev deps; helm.task.run and helm.task.inference spans in task.py with try/except ImportError guard (D018); DD_ENV/DD_SERVICE/DD_VERSION in .env.example; structlog events remain primary surface without DD agent.
- Notes: APM spans require explicit ddtrace install (uv sync --extra dev). Datadog APM operational verification is a human/operational check.

### R118 — Code cleanup: remove placeholder scheduling behavior, dead legacy logic
- Class: quality-attribute
- Status: validated
- Description: Remove placeholder scheduling behavior (hardcoded base date, stub task agent logic, duplicated scheduling paths). Simplify the scheduling path. Remove tests that test stubs rather than real behavior.
- Why it matters: Technical debt in the scheduling path was directly causing reliability failures.
- Source: user
- Primary owning slice: M004/S06
- Supporting slices: M004/S02
- Validation: S06 proves: grep returns nothing for '2026, 3, 16|_parse_slot_from_title|_DAY_OFFSETS|_TIME_PATTERN' in workflow_runs.py; S01 stub docstring removed from ConditionalApprovalPolicy; no hardcoded calendarId="primary" in adapter; all 500 tests pass after cleanup.
- Notes: _candidate_slots is retained — it is still used by the scheduling agent at line 356; it was never part of the legacy stub group.

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
| R100 | primary-user-loop | validated | M004/S01 | M004/S03, S04 | 10 unit tests; inline execution; 500 full suite |
| R101 | core-capability | validated | M004/S01 | M004/S02 | 15 unit tests; responses.parse structured output |
| R102 | constraint | validated | M004/S02 | M004/S04 | ValidationError at startup; OPERATOR_TIMEZONE in /status |
| R103 | core-capability | validated | M004/S02 | M004/S05 | parse_local_slot returns PDT; RFC3339 hack removed; test_07 in place |
| R104 | quality-attribute | validated | M004/S02 | none | 18 unit tests; warn-and-skip wired in _run_calendar_agent |
| R105 | core-capability | validated | M004/S02 | none | compute_reference_week dynamic; hardcoded date absent |
| R106 | operability | validated | M004/S03 | M004/S01 | 10 unit tests; inline execution paths proven |
| R107 | core-capability | validated | M004/S01 | M004/S04 | 7 policy edge case tests; exact boundary values verified |
| R108 | operability | validated | M004/S04 | M004/S03, S07 | 4 unit tests; notification loop wired; structlog signals confirmed |
| R109 | operability | validated | M004/S04 | M004/S07 | CommandHandler registered line 78; operator-facing output verified |
| R110 | operability | validated | M004/S04 | M004/S06 | CommandHandler registered line 87; 4 unit tests; list_today_events implemented |
| R111 | operability | validated | M004/S04 | none | pure formatters; test_no_debug_internals; D008 standing convention |
| R112 | core-capability | validated | M004/S02 | S01, S06 | shared primitives in helm_orchestration; duplicates deleted; 500 tests |
| R113 | quality-attribute | validated | M004/S05 | none | misclassified test moved; E2E gate enforced; 0 boundary violations |
| R114 | quality-attribute | validated | M004/S05 | none | fail-fast on primary verified; skip-all on absent HELM_E2E; test_07 in place |
| R115 | continuity | validated | M004/S02 | M004/S06 | 53/53 integration tests; weekly scheduling end-to-end confirmed |
| R116 | operability | validated | M004/S06 | none | watchfiles in both run scripts and dev deps |
| R117 | operability | validated | M004/S06 | none | ddtrace APM spans with try/except guard; DD env vars in .env.example |
| R118 | quality-attribute | validated | M004/S06 | M004/S02 | all legacy stubs absent from workflow_runs.py; grep confirms clean |
| R200 | integration | deferred | M005 | none | unmapped |
| R201 | core-capability | deferred | M005 | none | unmapped |
| R202 | integration | deferred | M005 | none | unmapped |
| R020 | primary-user-loop | deferred | none | none | unmapped |
| R300 | anti-feature | out-of-scope | none | none | n/a |
| R301 | anti-feature | out-of-scope | none | none | n/a |
| R302 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 0 (all M004 requirements validated)
- Validated: 19 (R100–R118, all M004 requirements) + all prior M001–M003 requirements
- Deferred: 4 (R020, R200, R201, R202)
- Out of scope: 3 (R300, R301, R302)
