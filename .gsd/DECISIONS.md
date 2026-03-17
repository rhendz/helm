# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

## M001–M003 Decisions (legacy format — preserved as-is)

- "Keep workflow persistence in dedicated workflow_* tables rather than extending legacy email-specific or observability tables."
- "Define the final summary artifact as a typed payload now, with nullable approval and downstream sync linkage fields, so later phases extend the same contract."
- "Model workflow artifacts and failures as explicit Pydantic schemas so storage payloads stay typed before specialist adapters exist."
- "Treat validation failures as blocked runs that require an explicit retry or terminate action instead of implicit worker progression."
- "Fail runnable steps durably when no step handler exists so adapter-free execution errors are visible in persisted state."
- "Kept API and Telegram workflow status behavior aligned behind one shared workflow read-model service."
- "Exposed paused workflow conditions explicitly as `paused_state` and nullable `pause_reason` instead of requiring clients to infer blocked vs failed runs from generic status text."
- "Used dedicated workflow run routes and bot commands for create, inspect, retry, and terminate actions instead of overloading unrelated status surfaces."
- "Persist specialist execution in a dedicated workflow_specialist_invocations table instead of hiding invocation metadata inside artifact payloads."
- "Move specialist execution into WorkflowOrchestrationService so the worker only registers workflow-semantic steps and resumes durable state."
- "Treat schedule proposals as first-class workflow artifacts validated by the same kernel flow as normalized tasks."
- "Approval checkpoints live in a dedicated workflow_approval_checkpoints table and are linked to approval request and decision artifacts."
- "Schedule proposals block the run at an explicit await_schedule_approval step instead of completing the workflow or reusing validation-failure semantics."
- "API and Telegram surfaces consume one checkpoint-aware workflow status projection and delegate all decision semantics back to the orchestration kernel."
- "Approval decisions now require the concrete proposal artifact id so operator actions cannot silently resolve against an implied latest version."
- "Revision requests create a dedicated revision_request artifact and the next schedule_proposal supersedes the prior proposal while staying in the same workflow run."
- "Approved proposal execution now materializes deterministic task and calendar sync records before any adapter call path runs."
- "Sync identity is anchored to proposal artifact id, proposal version, target system, sync kind, and planned item key with relational uniqueness."
- "Adapter protocols return normalized request, outcome, and reconciliation envelopes while orchestration retains ordering and retry policy."
- "Sync retries and restarts rebuild remaining work by querying persisted sync records scoped to the semantic step lineage, not an in-memory cursor."
- "Orchestration owns execution order, failure classification, and reconciliation policy while connectors expose only upsert and reconcile contracts."
- "Uncertain write outcomes stop the step as retryable and must reconcile durable identity before Helm attempts another outbound write."
- "Replay creates a new sync-row lineage generation for the same planned item so prior execution history stays queryable."
- "Termination after partial success cancels remaining sync work and records partial counts instead of rewriting succeeded rows."
- "Recovery classification lives on durable sync rows plus workflow events so app-layer projections do not infer semantics from free-form error text."
- "Workflow status projection reads sync counts, recovery class, and replay lineage directly from workflow_sync_records so operator surfaces do not parse workflow events."
- "Effect summaries stay compact and stable: total writes plus task/calendar counts before execution begins."
- "Terminal partial-sync state takes precedence over stale adapter error text when projecting operator-facing recovery summaries."
- "Explicit replay requests are validated against safe_next_actions from the shared workflow status projection before orchestration enqueues new sync lineage."
- "Worker replay jobs delegate workflow replay execution to the shared replay service so queue consumption does not invent replay policy."
- "Replay worker wiring for email triage uses build_email_agent_runtime as an injectable runtime_factory so tests and future slices can mock or constrain EmailAgent behavior without expanding its truth status."
- "Telegram surfaces replay by merging safe recovery actions with existing operator actions and exposing replay as a distinct command from retry."
- "Keep weekly scheduling request parsing deterministic and shared in the API status service so Telegram and API store the same durable contract."
- "Extend the shared schedule proposal schema with honored constraints, assumptions, carry-forward tasks, and rationale instead of hiding representative details inside free-form text."
- "Keep Telegram as a thin formatter over the shared status projection rather than introducing a representative-only read model."
- "Representative completed runs now persist a final summary artifact automatically when apply_schedule finishes."
- "Completion and recovery summaries read from durable proposal, approval, and sync persistence instead of stale event text."
- "Telegram completion output stays compact by preferring the shared completion summary over inline proposal detail dumps."
- "Replay-requested recovery classification now overrides stale final-summary success in the shared completion projection."
- "Representative final-summary artifacts stay unchanged after replay so lineage remains inspectable while live status turns recovery-oriented."
- "Telegram /workflows continues to format the shared completion summary instead of adding surface-specific replay semantics."
- "Treat weekly scheduling end-to-end behavior (API + worker + Telegram) as a protected core with dedicated integration tests and a reusable UAT script, so future cleanup can rely on automated plus human verification for task/calendar workflows."
- "Google Calendar auth model: use user OAuth (not service account) to match Gmail integration precedent, respect operator identity, and simplify permission scoping. Operator self-configures credentials (client_id, client_secret, refresh_token from Google Cloud Console) and stores in env vars (CALENDAR_CLIENT_ID, CALENDAR_CLIENT_SECRET, CALENDAR_REFRESH_TOKEN). Helm accesses operator's personal 'primary' calendar."
- "Calendar adapter protocol: reuse existing CalendarSystemAdapter interface (upsert_calendar_block, reconcile_calendar_block) with no changes to contracts.py. Adapter receives CalendarSyncRequest, returns CalendarSyncResult with Google event ID and retry disposition. Reconcile is read-only (drift detection only; updates deferred to S04 policy decision)."
- "Payload fingerprint for drift detection: canonical JSON representation of proposed event (title, start, end, description). Stored during proposal; compared against live calendar event state in reconcile to detect manual operator edits. Enables S02 passive drift detection without active write operations."
- "External object ID in upsert payload: GoogleCalendarAdapter reads external_object_id from payload dict (not ApprovedSyncItem). Allows tracking via database sync records without schema changes. First upsert has no external_object_id (creates new event); subsequent upserts include it (updates existing event)."
- "Datetime formatting standard: use datetime.isoformat() with tzinfo for RFC3339 compliance. Validate timezone presence before formatting (raise ValueError if naive). Supports both Z suffix (UTC) and ±HH:MM offset in input. Google Calendar API expects RFC3339 with timezone in event.start.dateTime and event.end.dateTime."
- "HTTP error classification in adapter: map status codes to retry disposition (404→TERMINAL, 429→RETRIABLE, 5xx→RETRIABLE, unknown→TERMINAL). Allows orchestration to apply consistent retry policy without adapter-specific backoff logic. Status code extracted from HttpError.resp.status or exception.status_code."
- "Service instance caching: GoogleCalendarAdapter._service initialized lazily on first upsert call, reused for subsequent calls. Avoids rebuilding discovery client per-call. Credentials refreshed via auth.get_refreshed_credentials() on each API call (transparent token lifecycle)."
- "Drift detection via continuous polling (not webhooks): Orchestration calls reconcile during the sync step to detect external changes passively. Avoids webhook endpoint management and Google signature validation overhead."
- "Polling interval: 60 seconds during active sync phases (configured in future worker scheduling). Trade-off: acceptable API quota impact (1 read per sync record per minute) for simpler infrastructure."
- "Fingerprint fields included in drift detection: title, start, end, description. These are the user-visible event properties that matter for drift. Additional fields (attachments, reminders, etc.) excluded to keep fingerprint stable and focused."
- "Fingerprint schema evolution: adding new fields to the fingerprint requires incrementing a fingerprint version number to avoid false drift positives when the schema changes. Current payload uses implicit version 1."
- "Drift detection can be evolved to webhooks in future phases if operator workflows create frequent manual edits and polling latency becomes unacceptable. Webhook infrastructure (Google signature validation, endpoint setup) is a larger investment but reduces API quota pressure."
- "Telegram sync timeline limited to 8 events inline in `/workflows` command for readability and Telegram 4096 char message limit. `/workflow_sync_detail` shows unlimited timeline for deep-dive inspection."
- "Sync status symbols (✓⚠✗⏳) chosen for at-a-glance visibility in Telegram messages. Aligns with existing Telegram UI patterns in workflows.py."
- "Sync timeline section appended to `/workflows` output after completion summary, before approval checkpoint. Backward compatible: no timeline section if no sync records exist (no clutter)."
- "Sync event query interface uses existing repository methods (list_for_run, list_for_run_by_type) instead of introducing new SQL. Minimizes change surface and reuses tested abstractions."
- "Formatter functions use defensive dict access (.get() with defaults) and isinstance() type checks. Pattern mirrors existing workflows.py to maintain consistency across formatters."
- "Sync query and formatter failures are isolated from command response. Exceptions logged separately; failures do not block run status display (fault-tolerant degradation)."
- "Reconciliation policy for drift: PASSIVE (operator-initiated recovery, not auto-proposal). When drift is detected (external event manually edited), sync record is marked DRIFT_DETECTED with recovery_classification=TERMINAL_FAILURE. Operator is presented with request_replay action in /workflows command."
- "Drift detection and recovery classification assigned in mark_drift_detected(): sync record status=DRIFT_DETECTED, recovery_classification=TERMINAL_FAILURE, completed_at and recovery_updated_at set."
- "Partial failure handling: 'leave dirty' semantics. When sync A succeeds, sync B fails, sync C pending: B is marked FAILED_TERMINAL, C is marked CANCELLED, workflow terminates with TERMINATED_AFTER_PARTIAL_SUCCESS."

## M004 Decisions

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| D001 | M004 | arch | Workflow engine for M004 | Keep custom DB-backed step runner | Issues are implementation quality problems (hardcoded dates, UTC misuse, stub inference), not architecture problems. Temporal migration deferred indefinitely. | Yes — if step runner proves fundamentally inadequate for M005 requirements |
| D002 | M004 | arch | `/task` storage model | Workflow artifact (reuse existing machinery) | Avoids schema migration for M004. Dedicated tasks table deferred to M005 when task querying becomes a first-class need. | Yes — M005 likely needs dedicated table |
| D003 | M004 | arch | Immediate execution delivery | Inline from Telegram handler after DB persist | Operator-triggered actions execute immediately. Worker polling retained as background recovery for orphaned runnable steps. Crash safety: step state is DB-persisted; polling recovers. | Yes — revisit if bot process stability becomes a concern |
| D004 | M004 | arch | Shared scheduling primitives location | `packages/orchestration/src/helm_orchestration/scheduling.py` (new file) | Single import point for both `/task` handler and worker job handlers. Keeps timezone, inference, approval policy, and past-event guard co-located. | No |
| D005 | M004 | convention | Operator timezone config | `OPERATOR_TIMEZONE` env var (IANA format), required, fail-fast | Explicit source of truth. No inference from Telegram locale or system TZ. Validated against `zoneinfo` at startup. Visible in `/status` output. | No |
| D006 | M004 | convention | Conditional approval thresholds | Auto-place: confidence ≥ high AND block ≤ 2h AND no displacement. Ask: low confidence, ambiguous sizing, block >2h, conflict/displacement, unclear interpretation | Conservative policy while trust is being rebuilt. Exact confidence threshold is implementation detail for S01. | Yes — loosen once track record is established |
| D007 | M004 | convention | Test layer enforcement | unit: no DB/network; integration: test Postgres, no external API; e2e: real APIs, requires `HELM_E2E=true` + `HELM_CALENDAR_TEST_ID` | Prevents mock leakage that caused timezone bug to go undetected. E2E tests skip (not fail) if env vars absent, but fail explicitly if `HELM_CALENDAR_TEST_ID=primary`. | No |
| D008 | M004 | convention | Telegram default output | Concise operator-facing by default; debug/detail on explicit request | Current verbosity (run IDs, step names, sync timelines) makes Helm feel like a debugging tool. Detail remains accessible via existing `/workflow_sync_detail`, `/workflows` commands. | No |
| D009 | M004 | library | Observability for M004 | `ddtrace` for APM + Datadog log forwarding | Structured JSON logs already present via structlog. `ddtrace` adds APM traces with minimal code changes. Scope bounded to `/task` path + key request handlers. | Yes — expand scope in later milestones |
| D010 | M004 | convention | Live reload mechanism | `watchfiles` for worker and bot | API already uses uvicorn `--reload`. Worker and bot use `python -m watchfiles helm_worker.main src/` pattern. Add `watchfiles` to dev deps. | No |
