---
phase: 01
slug: durable-workflow-foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-12
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/integration/test_workflow_status_routes.py` |
| **Full suite command** | `uv run --frozen --extra dev pytest` |
| **Estimated runtime** | ~30-90 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/integration/test_workflow_status_routes.py`
- **After every plan wave:** Run `uv run --frozen --extra dev pytest`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | FLOW-01, FLOW-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py` | ✅ | ⬜ pending |
| 01-01-02 | 01 | 1 | ARTF-01, ARTF-02, ARTF-03, ARTF-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py -k 'final summary or execution failure'` | ✅ | ⬜ pending |
| 01-02-01 | 02 | 2 | AGNT-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k validation` | ✅ | ⬜ pending |
| 01-02-02 | 02 | 2 | AGNT-05, FLOW-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_agent_run_lifecycle.py -k 'validation_failed or execution failure'` | ✅ | ⬜ pending |
| 01-02-03 | 02 | 2 | AGNT-06, ARTF-03, ARTF-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_worker_registry.py` | ✅ | ⬜ pending |
| 01-02-04 | 02 | 2 | FLOW-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k 'retry or terminate or execution failure'` | ✅ | ⬜ pending |
| 01-03-01 | 03 | 3 | FLOW-02, ARTF-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py` | ✅ | ⬜ pending |
| 01-03-02 | 03 | 3 | FLOW-04, AGNT-06 | integration | `uv run --frozen --extra dev pytest tests/integration/test_workflow_status_routes.py tests/unit/test_api_status.py -k 'blocked or failed'` | ✅ | ⬜ pending |
| 01-03-03 | 03 | 3 | FLOW-02, FLOW-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_telegram_commands.py tests/unit/test_workflow_status_service.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_workflow_repositories.py` — repository coverage for `workflow_runs`, `workflow_steps`, and `workflow_artifacts`
- [ ] `tests/unit/test_workflow_orchestration_service.py` — core run/step transition, validation-blocking, and ordinary execution-failure coverage
- [ ] `tests/unit/test_workflow_status_service.py` — triage-oriented read model coverage for API/Telegram summaries
- [ ] `tests/unit/test_telegram_commands.py` — Telegram command coverage for workflow start, summary, and retry/terminate interactions
- [ ] `tests/integration/test_workflow_status_routes.py` — route-level coverage for run list/detail inspection, including blocked and failed-step detail payloads

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram triage summary is concise and actionable | FLOW-02 | Existing Telegram interaction quality is easier to judge manually than snapshot-test first | Start local bot wiring or inspect formatter output, then verify the summary answers: what run, what step, what happened last, does it need action, and what recovery action is next |
| Run lineage is understandable from the API detail view | FLOW-02, ARTF-05 | Operator readability is partly presentational | Create a sample run, inspect API payload, and verify step sequence, artifact versions, validation outcome, and recovery options are intelligible without DB queries |
| Blocked-run retry/terminate flows are explicit and safe in operator surfaces | FLOW-04, AGNT-06 | Human approval wording and operator ergonomics should be checked end-to-end | Trigger a blocked validation failure, invoke API and Telegram retry/terminate actions, and confirm only the chosen action changes durable run state |
| Ordinary execution-failure triage reads clearly in operator surfaces | FLOW-04 | Human operators need to distinguish failed execution from blocked validation quickly | Trigger a step exception before validation output is produced, inspect API and Telegram views, and verify they show failed step, error summary, retryability, and next allowed action without labeling it as `validation_failed` |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Automated coverage includes ordinary execution failure persistence, not only blocked validation failures

**Approval:** pending
