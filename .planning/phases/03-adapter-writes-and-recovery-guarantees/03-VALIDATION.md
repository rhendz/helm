---
phase: 03
slug: adapter-writes-and-recovery-guarantees
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-13
---

# Phase 03 — Validation Strategy

> Reconstructed Nyquist validation contract for the completed adapter-writes and recovery phase.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_replay_service.py tests/unit/test_worker_registry.py tests/integration/test_workflow_status_routes.py` |
| **Full suite command** | `uv run --frozen --extra dev pytest` |
| **Estimated runtime** | ~5 seconds for the phase slice |

---

## Sampling Rate

- **After every task commit:** Run `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_replay_service.py tests/unit/test_worker_registry.py tests/integration/test_workflow_status_routes.py`
- **After every plan wave:** Run `uv run --frozen --extra dev pytest`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | SYNC-01, SYNC-02, SYNC-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py -k sync` | ✅ | ✅ green |
| 03-01-02 | 01 | 1 | SYNC-01, SYNC-02 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k adapter` | ✅ | ✅ green |
| 03-01-03 | 01 | 1 | SYNC-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_repositories.py -k 'approved_sync_manifest_created or sync'` | ✅ | ✅ green |
| 03-02-01 | 02 | 2 | SYNC-04, SYNC-05, RCVR-01, RCVR-02 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py -k 'sync and retry'` | ✅ | ✅ green |
| 03-02-02 | 02 | 2 | SYNC-06, RCVR-01, RCVR-02 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k 'sync or reconciliation or retry'` | ✅ | ✅ green |
| 03-02-03 | 02 | 2 | SYNC-04, SYNC-05, RCVR-01, RCVR-02 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_repositories.py` | ✅ | ✅ green |
| 03-03-01 | 03 | 3 | RCVR-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k 'replay or recoverable or terminal'` | ✅ | ✅ green |
| 03-03-02 | 03 | 3 | RCVR-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k 'terminate or partial'` | ✅ | ✅ green |
| 03-03-03 | 03 | 3 | RCVR-03 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k 'retry or replay or terminate'` | ✅ | ✅ green |
| 03-04-01 | 04 | 4 | OPER-01 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py -k 'effect or sync or replay'` | ✅ | ✅ green |
| 03-04-02 | 04 | 4 | OPER-01 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py -k 'partial or terminal or lineage'` | ✅ | ✅ green |
| 03-04-03 | 04 | 4 | OPER-01 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py` | ✅ | ✅ green |
| 03-05-01 | 05 | 5 | RCVR-04, OPER-01 | unit | `uv run --frozen --extra dev pytest tests/unit/test_replay_service.py -k api` | ✅ | ✅ green |
| 03-05-02 | 05 | 5 | RCVR-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_replay_service.py -k worker` | ✅ | ✅ green |
| 03-05-03 | 05 | 5 | OPER-01, RCVR-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py -k telegram` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- None. Existing sync-record, orchestration, status-projection, replay-service, Telegram, worker-registry, and integration-route tests already cover the phase requirements.

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

- `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_replay_service.py tests/unit/test_worker_registry.py tests/integration/test_workflow_status_routes.py`
- Result: `97 passed in 4.90s`
