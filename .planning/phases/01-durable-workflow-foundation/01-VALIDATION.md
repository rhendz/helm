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
| **Quick run command** | `uv run --frozen --extra dev pytest tests/unit/test_storage_repositories.py tests/unit/test_api_status.py tests/unit/test_artifact_trace_service.py` |
| **Full suite command** | `uv run --frozen --extra dev pytest` |
| **Estimated runtime** | ~30-90 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --frozen --extra dev pytest tests/unit/test_storage_repositories.py tests/unit/test_api_status.py tests/unit/test_artifact_trace_service.py`
- **After every plan wave:** Run `uv run --frozen --extra dev pytest`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | FLOW-01 | unit | `uv run --frozen --extra dev pytest tests/unit/test_storage_repositories.py` | ✅ | ⬜ pending |
| 01-01-02 | 01 | 1 | FLOW-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_storage_repositories.py tests/unit/test_agent_run_lifecycle.py` | ✅ | ⬜ pending |
| 01-01-03 | 01 | 1 | ARTF-01 | unit | `uv run --frozen --extra dev pytest tests/unit/test_storage_repositories.py tests/unit/test_artifact_trace_service.py` | ✅ | ⬜ pending |
| 01-01-04 | 01 | 1 | ARTF-02 | unit | `uv run --frozen --extra dev pytest tests/unit/test_storage_repositories.py tests/unit/test_artifact_trace_service.py` | ✅ | ⬜ pending |
| 01-01-05 | 01 | 1 | ARTF-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_storage_repositories.py tests/unit/test_artifact_trace_service.py` | ✅ | ⬜ pending |
| 01-01-06 | 01 | 1 | ARTF-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_storage_repositories.py tests/unit/test_artifact_trace_service.py` | ✅ | ⬜ pending |
| 01-02-01 | 02 | 1 | AGNT-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_artifact_trace_service.py` | ✅ | ⬜ pending |
| 01-02-02 | 02 | 1 | AGNT-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_artifact_trace_service.py tests/unit/test_agent_run_lifecycle.py` | ✅ | ⬜ pending |
| 01-02-03 | 02 | 1 | AGNT-06 | unit | `uv run --frozen --extra dev pytest tests/unit/test_artifact_trace_service.py tests/unit/test_api_status.py` | ✅ | ⬜ pending |
| 01-02-04 | 02 | 1 | FLOW-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_agent_run_lifecycle.py tests/unit/test_api_status.py` | ✅ | ⬜ pending |
| 01-03-01 | 03 | 2 | FLOW-02 | integration | `uv run --frozen --extra dev pytest tests/integration/test_routes.py tests/unit/test_api_status.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_workflow_repositories.py` — repository coverage for `workflow_runs`, `workflow_steps`, and `workflow_artifacts`
- [ ] `tests/unit/test_workflow_orchestration_service.py` — core run/step transition and validation-blocking coverage
- [ ] `tests/unit/test_workflow_status_service.py` — triage-oriented read model coverage for API/Telegram summaries
- [ ] `tests/integration/test_workflow_status_routes.py` — route-level coverage for run list/detail inspection

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram triage summary is concise and actionable | FLOW-02 | Existing Telegram interaction quality is easier to judge manually than snapshot-test first | Start local bot wiring or inspect formatter output, then verify the summary answers: what run, what step, what happened last, does it need action |
| Run lineage is understandable from the API detail view | FLOW-02, ARTF-05 | Operator readability is partly presentational | Create a sample run, inspect API payload, and verify step sequence, artifact versions, and validation outcome are intelligible without DB queries |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
