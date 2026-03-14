---
phase: 02
slug: specialist-dispatch-and-approval-semantics
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-13
---

# Phase 02 — Validation Strategy

> Reconstructed Nyquist validation contract for the completed specialist-dispatch and approval phase.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_worker_registry.py tests/integration/test_workflow_status_routes.py` |
| **Full suite command** | `uv run --frozen --extra dev pytest` |
| **Estimated runtime** | ~5 seconds for the phase slice |

---

## Sampling Rate

- **After every task commit:** Run `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_worker_registry.py tests/integration/test_workflow_status_routes.py`
- **After every plan wave:** Run `uv run --frozen --extra dev pytest`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | AGNT-03, ARTF-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py -k 'specialist or proposal or invocation'` | ✅ | ✅ green |
| 02-01-02 | 01 | 1 | AGNT-01, AGNT-02, DEMO-02, DEMO-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k 'task_agent or calendar_agent or specialist'` | ✅ | ✅ green |
| 02-01-03 | 01 | 1 | AGNT-03, DEMO-02, DEMO-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_worker_registry.py tests/unit/test_workflow_repositories.py` | ✅ | ✅ green |
| 02-02-01 | 02 | 2 | APRV-01, APRV-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py -k approval` | ✅ | ✅ green |
| 02-02-02 | 02 | 2 | APRV-01, APRV-02, APRV-03, APRV-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k approval` | ✅ | ✅ green |
| 02-02-03 | 02 | 2 | APRV-02, APRV-04 | integration | `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/integration/test_workflow_status_routes.py` | ✅ | ✅ green |
| 02-03-01 | 03 | 3 | APRV-05, ARTF-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k revision` | ✅ | ✅ green |
| 02-03-02 | 03 | 3 | APRV-06 | integration | `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py tests/integration/test_workflow_status_routes.py -k version` | ✅ | ✅ green |
| 02-03-03 | 03 | 3 | APRV-05, APRV-06 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/integration/test_workflow_status_routes.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- None. Existing workflow repository, orchestration, status, Telegram, worker-registry, and route coverage already cover the phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-13

## Validation Audit 2026-03-13

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

## Evidence

- `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_worker_registry.py tests/integration/test_workflow_status_routes.py`
- Result: `92 passed in 4.41s`
