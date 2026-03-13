---
phase: 04
slug: representative-scheduling-workflow
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_replay_service.py` |
| **Full suite command** | `scripts/test.sh` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py tests/unit/test_telegram_commands.py tests/unit/test_replay_service.py`
- **After every plan wave:** Run `scripts/test.sh`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | DEMO-01 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k weekly_scheduling` | ✅ | ⬜ pending |
| 04-01-02 | 01 | 1 | DEMO-01 | integration | `uv run --frozen --extra dev pytest tests/integration/test_workflow_status_routes.py -k 'create and weekly_scheduling'` | ✅ | ⬜ pending |
| 04-01-03 | 01 | 1 | DEMO-04 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py -k 'approval or sync'` | ✅ | ⬜ pending |
| 04-02-01 | 02 | 2 | DEMO-05 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_workflow_status_service.py -k revision` | ✅ | ⬜ pending |
| 04-02-02 | 02 | 2 | DEMO-06 | unit | `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_replay_service.py -k 'summary or replay or recovery or apply_schedule'` | ✅ | ⬜ pending |
| 04-02-03 | 02 | 2 | DEMO-06 | integration | `uv run --frozen --extra dev pytest tests/integration/test_workflow_status_routes.py -k 'weekly_scheduling or summary or lineage'` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_workflow_orchestration_service.py` — extend representative-flow coverage for real weekly request parsing and final summary linkage
- [ ] `tests/unit/test_workflow_status_service.py` — cover compact proposal/completion summaries and version visibility for the representative flow
- [ ] `tests/unit/test_telegram_commands.py` — cover Telegram start and approval/revision command behavior for `weekly_scheduling`
- [ ] `tests/integration/test_workflow_status_routes.py` — ensure API create/detail flows expose representative workflow details and share request-contract semantics with Telegram start

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram request UX feels compact but sufficient for a weekly plan decision | DEMO-01 | Command text and summary readability are hard to judge from assertions alone | Start a representative workflow from Telegram-style input, inspect the initial status reply, and confirm the request/constraint shape is understandable without extra tooling. |
| Proposal checkpoint is fast to act on while still honest about carry-forward work and assumptions | DEMO-04, DEMO-05 | Operator clarity and message density are product judgments | Generate a proposal, inspect the Telegram summary, request a revision, then inspect the revised proposal summary for artifact targeting, assumptions, and carry-forward visibility. |
| Completion summary foregrounds outcome while keeping lineage inspectable on demand | DEMO-06 | Default-summary usefulness is a UX judgment rather than a pure contract check | Complete an approved run and inspect the Telegram/API completion views to confirm outcome-first messaging, visible carry-forward items, accessible lineage detail, and accurate task/calendar sync highlights. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
