---
phase: 01
slug: durable-workflow-foundation
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-12
---

# Phase 01 — Validation Strategy

> Audited Nyquist validation contract for the completed durable-workflow-foundation phase.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/integration/test_workflow_status_routes.py` |
| **Full suite command** | `uv run --frozen --extra dev pytest` |
| **Estimated runtime** | ~5 seconds for the phase slice |

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
| 01-01-01 | 01 | 1 | FLOW-01, FLOW-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py` | ✅ | ✅ green |
| 01-01-02 | 01 | 1 | ARTF-01, ARTF-02, ARTF-03, ARTF-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py -k 'final summary or execution failure'` | ✅ | ✅ green |
| 01-02-01 | 02 | 2 | AGNT-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k validation` | ✅ | ✅ green |
| 01-02-02 | 02 | 2 | AGNT-05, FLOW-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_agent_run_lifecycle.py -k 'validation_failed or execution failure'` | ✅ | ✅ green |
| 01-02-03 | 02 | 2 | AGNT-06, ARTF-03, ARTF-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_worker_registry.py` | ✅ | ✅ green |
| 01-02-04 | 02 | 2 | FLOW-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k 'retry or terminate or execution failure'` | ✅ | ✅ green |
| 01-03-01 | 03 | 3 | FLOW-02, ARTF-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py` | ✅ | ✅ green |
| 01-03-02 | 03 | 3 | FLOW-04, AGNT-06 | integration | `uv run --frozen --extra dev pytest tests/integration/test_workflow_status_routes.py tests/unit/test_api_status.py -k 'blocked or failed'` | ✅ | ✅ green |
| 01-03-03 | 03 | 3 | FLOW-02, FLOW-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_telegram_commands.py tests/unit/test_workflow_status_service.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- None. Existing repository, orchestration, API, Telegram, worker-registry, and integration-route tests cover the phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram triage summary is concise and actionable | FLOW-02 | Operator readability is still a product judgment beyond contract tests | Start local bot wiring or inspect formatter output, then verify the summary answers: what run, what step, what happened last, does it need action, and what recovery action is next |
| Run lineage is understandable from the API detail view | FLOW-02, ARTF-05 | Payload readability is partly presentational | Create a sample run, inspect API payload, and verify step sequence, artifact versions, validation outcome, and recovery options are intelligible without DB queries |
| Blocked-run retry/terminate flows are explicit and safe in operator surfaces | FLOW-04, AGNT-06 | Operator ergonomics are better judged end to end by a human | Trigger a blocked validation failure, invoke API and Telegram retry/terminate actions, and confirm only the chosen action changes durable run state |
| Ordinary execution-failure triage reads clearly in operator surfaces | FLOW-04 | Human operators should confirm failed execution is distinct from blocked validation | Trigger a step exception before validation output is produced, inspect API and Telegram views, and verify they show failed step, error summary, retryability, and next allowed action without labeling it as `validation_failed` |

These checks are supplemental product-quality reviews. They do not represent missing automated Nyquist coverage for Phase 1 requirements.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Automated coverage includes ordinary execution failure persistence, not only blocked validation failures

**Approval:** approved 2026-03-13

## Validation Audit 2026-03-13

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

## Evidence

- `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/integration/test_workflow_status_routes.py tests/unit/test_api_status.py tests/unit/test_agent_run_lifecycle.py tests/unit/test_worker_registry.py`
- Result: `95 passed in 3.71s`
