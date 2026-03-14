# Project Research Summary

**Project:** Helm Orchestration Kernel v1
**Domain:** Durable orchestration kernel for a personal AI workflow system
**Researched:** 2026-03-11
**Confidence:** HIGH

## Executive Summary

This project is not a generic agent platform and should not be treated like one. The right approach is to turn Helm's existing Python, Postgres, FastAPI, worker, and Telegram foundation into a real orchestration kernel with durable workflow state, typed artifacts, approval-aware pause/resume semantics, and adapter-isolated side effects.

The strongest ecosystem fit is to keep the current repo stack and add a real kernel boundary in `packages/orchestration`, using LangGraph's durable execution and interrupt semantics where they help, while preserving Helm-owned storage tables and repositories as the source of truth. The core risk is fake durability: a workflow that looks resumable but cannot actually survive restarts, retries, or approval pauses without duplicate writes or manual repair.

## Key Findings

### Recommended Stack

The recommended stack is conservative on purpose: Python 3.11, FastAPI, PostgreSQL, SQLAlchemy 2.0.x, LangGraph 1.0.x, structured provider calls through Helm's LLM layer, and Telegram as the operator surface. That aligns with both the current repo and the domain's actual needs.

**Core technologies:**
- Python 3.11: primary runtime — already established in the repo
- PostgreSQL 17.x on current minor: durable workflow and artifact store — safest fit for DB-first lineage
- SQLAlchemy 2.0.48: repository and transaction boundary — stable current line
- FastAPI 0.128.x: internal control plane — suitable for run inspection, replay, and approval endpoints
- LangGraph 1.0.x: durable execution and interrupts — strongest fit for pause/resume semantics

### Expected Features

The kernel's table stakes are clear: durable runs, step-level artifacts, specialist dispatch, approval checkpoints, adapter-based writes, and failure recovery. The differentiators are typed plug-in specialists and full side-effect lineage, not more end-user features.

**Must have (table stakes):**
- Durable workflow run lifecycle — users expect restart safety
- Approval-aware pause/resume — required by Helm's safety contract
- Structured artifacts and lineage — required for inspection and replay
- Adapter-gated side effects — required for clean external writes

**Should have (competitive):**
- Typed specialist contract — makes future agents easy to add
- Replayable scheduling demo — proves the kernel with a real workflow

**Defer (v2+):**
- More autonomous branching
- Broader workflow catalog
- New UI surfaces beyond Telegram/API

### Architecture Approach

The right architecture is layered: app entry points trigger workflows, `packages/orchestration` owns the lifecycle, `packages/agents` own specialist logic, `packages/storage` own durable state, and connectors/adapters own side effects. This keeps approval, recovery, and replay semantics reusable instead of burying them inside domain-specific code.

**Major components:**
1. Workflow kernel — run lifecycle, step transitions, interrupts, resume, replay
2. Specialist agents — bounded task normalization and scheduling logic
3. Durable persistence — run state, artifacts, approvals, sync records
4. External adapters — task-system and calendar writes with idempotent boundaries

### Critical Pitfalls

1. **Fake durability** — persist every major transition, not just final artifacts
2. **Duplicate external writes on retry** — use adapter-side idempotency and sync records
3. **Kernel logic trapped in domain packages** — extract lifecycle ownership into `packages/orchestration`
4. **Approval as UI-only** — make decisions durable kernel state
5. **Unchecked agent output** — normalize and validate before downstream execution

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Durable Workflow Foundation
**Rationale:** Everything else depends on a trustworthy run model.
**Delivers:** Workflow run schema, step state, artifact persistence, validation boundaries
**Addresses:** durable lifecycle, typed artifacts, restart-safe state
**Avoids:** fake durability and unchecked agent output

### Phase 2: Specialist Dispatch And Approval Semantics
**Rationale:** Once the lifecycle exists, the kernel can own typed specialist steps and pause/resume decisions.
**Delivers:** `TaskAgent` and `CalendarAgent` invocation contracts, approval requests, resume/reject/revise flow
**Uses:** LangGraph interrupts or equivalent kernel pause/resume semantics
**Implements:** reusable orchestration boundary

### Phase 3: Adapter Writes And Recovery
**Rationale:** External writes should come only after specialist outputs and approvals are stable.
**Delivers:** task/calendar adapters, sync lineage, idempotent writes, failure and replay handling
**Uses:** existing worker/replay patterns plus adapter repositories
**Implements:** safe side-effect execution

### Phase 4: Representative Scheduling Workflow
**Rationale:** The kernel needs a real end-to-end workflow to prove it.
**Delivers:** task-to-week scheduling flow from raw request to approved external writes
**Uses:** all prior kernel layers together

### Phase Ordering Rationale

- Durable state must precede approval and replay, or those later phases become cosmetic.
- Specialist invocation should precede adapters so external writes consume typed, validated artifacts.
- The representative workflow should land after the kernel primitives exist, so it validates the architecture instead of dictating it prematurely.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** exact LangGraph interrupt/checkpointer integration and how much of it Helm should own directly
- **Phase 3:** adapter idempotency and reconciliation strategy per downstream system

Phases with standard patterns (skip research-phase):
- **Phase 1:** workflow tables, repositories, typed schemas, and explicit status transitions are straightforward

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Strong overlap between current repo and current ecosystem guidance |
| Features | HIGH | The kernel requirements are clear and directly implied by the product contract |
| Architecture | HIGH | Current repo boundaries already suggest the right extraction path |
| Pitfalls | HIGH | The main failure modes are well-understood for durable workflow systems |

**Overall confidence:** HIGH

### Gaps to Address

- LangGraph should support the kernel, not replace Helm-owned artifact semantics — validate that boundary during planning.
- The exact workflow schema vocabulary should be chosen early so new tables do not duplicate existing email-specific artifacts unnecessarily.

## Sources

### Primary (HIGH confidence)
- LangGraph durable execution docs — https://docs.langchain.com/oss/python/langgraph/durable-execution
- LangGraph human-in-the-loop docs — https://docs.langchain.com/oss/python/langgraph/human-in-the-loop
- SQLAlchemy current docs — https://docs.sqlalchemy.org/20/intro.html
- PostgreSQL versioning policy — https://www.postgresql.org/support/versioning/
- OpenAI Responses API docs — https://platform.openai.com/docs/api-reference/responses/list

### Secondary (MEDIUM confidence)
- FastAPI official GitHub releases — https://github.com/fastapi/fastapi
- python-telegram-bot official releases — https://github.com/python-telegram-bot/python-telegram-bot/releases
- OpenAI agent tooling announcement — https://openai.com/index/new-tools-for-building-agents/
- LangGraph 1.0 GA announcement — https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available

### Tertiary (LOW confidence)
- Existing Helm codebase maps in `.planning/codebase/` — inference about the best extraction path from the current repo state

---
*Research completed: 2026-03-11*
*Ready for roadmap: yes*
