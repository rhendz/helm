---
phase: 04
slug: representative-scheduling-workflow
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-13
---

# Phase 04 — Validation Strategy

> Audited Nyquist validation contract for the completed representative-scheduling-workflow phase.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_replay_service.py` |
| **Full suite command** | `scripts/test.sh` |
| **Estimated runtime** | ~5 seconds for the phase slice |

---

## Sampling Rate

- **After every task commit:** Run `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_replay_service.py`
- **After every plan wave:** Run `scripts/test.sh`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | DEMO-01 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k weekly_scheduling` | ✅ | ✅ green |
| 04-01-02 | 01 | 1 | DEMO-01 | integration | `uv run --frozen --extra dev pytest tests/integration/test_workflow_status_routes.py -k 'create and weekly_scheduling'` | ✅ | ✅ green |
| 04-01-03 | 01 | 1 | DEMO-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py -k 'approval or sync'` | ✅ | ✅ green |
| 04-02-01 | 02 | 2 | DEMO-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py -k revision` | ✅ | ✅ green |
| 04-02-02 | 02 | 2 | DEMO-06 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_replay_service.py -k 'summary or replay or recovery or apply_schedule'` | ✅ | ✅ green |
| 04-02-03 | 02 | 2 | DEMO-06 | integration | `uv run --frozen --extra dev pytest tests/integration/test_workflow_status_routes.py -k 'weekly_scheduling or summary or lineage'` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- None. Existing orchestration, status-projection, Telegram, replay, and integration-route tests cover the phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram request UX feels compact but sufficient for a weekly plan decision | DEMO-01 | Readability and operator confidence remain product judgments beyond contract tests | Start a representative workflow from Telegram-style input, inspect the initial status reply, and confirm the request/constraint shape is understandable without extra tooling. |
| Proposal checkpoint is fast to act on while still honest about carry-forward work and assumptions | DEMO-04, DEMO-05 | Summary density and approval ergonomics are better judged end-to-end by a human | Generate a proposal, inspect the Telegram summary, request a revision, then inspect the revised proposal summary for artifact targeting, assumptions, and carry-forward visibility. |
| Completion summary foregrounds outcome while keeping lineage inspectable on demand | DEMO-06 | Outcome-first usefulness is a UX judgment rather than a missing automated contract | Complete an approved run and inspect the Telegram/API completion views to confirm outcome-first messaging, visible carry-forward items, accessible lineage detail, and accurate task/calendar sync highlights. |

These checks are supplemental product-quality reviews. They do not represent missing automated Nyquist coverage for Phase 4 requirements.

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

- `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_replay_service.py tests/integration/test_workflow_status_routes.py`
- Result: `85 passed in 4.11s`
