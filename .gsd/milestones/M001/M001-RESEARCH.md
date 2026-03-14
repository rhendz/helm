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

# Architecture Research

**Domain:** Durable orchestration kernel for a personal AI workflow system
**Researched:** 2026-03-11
**Confidence:** HIGH

## Standard Architecture

### System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Operator / Control Layer                │
├─────────────────────────────────────────────────────────────┤
│  Telegram Commands   Internal API   Replay / Status APIs   │
└──────────────┬──────────────┬──────────────┬───────────────┘
               │              │              │
┌──────────────┴──────────────┴──────────────┴───────────────┐
│                   Orchestration Kernel Layer               │
├─────────────────────────────────────────────────────────────┤
│  Run Lifecycle  Step Engine  Interrupts  Resume  Replay    │
│  Validation     Approval     Error Policy  Lineage         │
└──────────────┬──────────────┬──────────────┬───────────────┘
               │              │              │
┌──────────────┴──────────────┴──────────────┴───────────────┐
│                    Specialist Agent Layer                  │
├─────────────────────────────────────────────────────────────┤
│    TaskAgent                CalendarAgent                  │
│    future specialists via the same invocation contract     │
└──────────────┬──────────────┬──────────────┬───────────────┘
               │              │              │
┌──────────────┴──────────────┴──────────────┴───────────────┐
│                 Persistence + Integration Layer            │
├─────────────────────────────────────────────────────────────┤
│ Workflow tables  Artifact store  Approval records          │
│ Adapter sync log Task adapter    Calendar adapter          │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Orchestration kernel | Owns workflow runs, step transitions, pause/resume, and failure policy | `packages/orchestration` with explicit runtime contracts |
| Specialist agents | Produce typed outputs for bounded domain decisions | `packages/agents` subpackages with strict input/output schemas |
| Artifact persistence | Stores workflow state, artifacts, approvals, and sync lineage | `packages/storage` repositories and SQLAlchemy models |
| Adapters | Execute external side effects with idempotent boundaries | `packages/connectors` or dedicated adapter modules with sync records |
| Operator surfaces | Trigger, inspect, approve, replay, and resume runs | FastAPI routes and Telegram commands |

## Recommended Project Structure

```text
packages/
├── orchestration/
│   └── src/helm_orchestration/
│       ├── runtime.py         # kernel contracts and step executor interfaces
│       ├── workflows/         # reusable workflow definitions
│       ├── steps/             # step orchestration and transition logic
│       ├── approvals/         # pause/resume decision handling
│       ├── recovery/          # replay, retry, and failure policy
│       └── schemas/           # typed workflow payloads
├── agents/
│   └── src/
│       ├── task_agent/        # task normalization specialist
│       └── calendar_agent/    # scheduling specialist
├── storage/
│   └── src/helm_storage/
│       ├── models.py          # workflow and artifact tables
│       └── repositories/      # workflow persistence APIs
└── connectors/
    └── src/helm_connectors/
        ├── task_system/       # task adapter implementations
        └── calendar/          # calendar adapter implementations
```

### Structure Rationale

- **`packages/orchestration/`:** should become the real kernel boundary instead of leaving workflow ownership inside domain-specific agent code.
- **`packages/agents/`:** should hold bounded specialist behavior, not overall workflow lifecycle decisions.
- **`packages/storage/`:** should remain the durable system of record and own transaction-safe repositories.
- **`packages/connectors/`:** should keep external systems behind adapters so side effects stay isolated and auditable.

## Architectural Patterns

### Pattern 1: Durable State Machine

**What:** Explicit workflow states and step transitions persisted after each major boundary.
**When to use:** Always for long-running, approval-aware, or externally integrated workflows.
**Trade-offs:** More schema and lifecycle code, but much safer replay and inspection.

**Example:**
```python
run = workflow_repo.create_run(...)
workflow_repo.record_step(run.id, step="task_structuring", status="running")
```

### Pattern 2: Interrupt Before Side Effect

**What:** Pause execution before any meaningful external write and resume only with a persisted decision.
**When to use:** For calendar creation, task updates, message sending, or other user-visible side effects.
**Trade-offs:** Adds operator latency, but preserves user control and replay safety.

**Example:**
```python
decision = approval_service.request(run_id=run.id, action="write_calendar_blocks")
if decision.status == "paused":
    return interrupt_payload
```

### Pattern 3: Typed Artifact Boundary

**What:** Every specialist output is normalized into typed artifacts before downstream use.
**When to use:** Between agent outputs and validation, scheduling, or adapters.
**Trade-offs:** Requires more schema discipline, but prevents prompt-shaped leakage into the rest of the system.

## Data Flow

### Request Flow

```text
User request
    ↓
Telegram/API entry point
    ↓
Workflow run created
    ↓
TaskAgent step
    ↓
Validated task artifact
    ↓
CalendarAgent step
    ↓
Schedule proposal artifact
    ↓
Approval checkpoint
    ↓
Adapters execute side effects
    ↓
Sync records + final summary
```

### State Management

```text
Workflow tables
    ↓ (load)
Kernel executor
    ↓ (persist)
Artifacts / approvals / sync records
    ↓ (inspect)
Telegram + API status surfaces
```

### Key Data Flows

1. **Workflow lifecycle:** entry point creates run metadata, step state, and raw input artifacts.
2. **Specialist invocation:** kernel passes typed input to a specialist and records invocation metadata plus structured result.
3. **Approval flow:** kernel emits a pending approval request, pauses run execution, then resumes after a persisted decision.
4. **Adapter sync flow:** adapter writes create external IDs and result records linked back to the originating run and step.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single user / V1 | Monorepo, single Postgres, polling worker, Telegram-first control surface are sufficient |
| Heavier personal usage | Improve job isolation, replay tooling, and queue discipline before adding new infrastructure |
| Multi-user / broader platform | Reconsider tenancy, queueing, auth, and stronger workflow infrastructure only after V1 proves the kernel model |

### Scaling Priorities

1. **First bottleneck:** duplicate or unsafe side effects on retries — solve with idempotent adapter boundaries and persisted sync records.
2. **Second bottleneck:** workflow sprawl across packages — solve by moving lifecycle ownership into `packages/orchestration`.

## Anti-Patterns

### Anti-Pattern 1: Domain Workflow Owns the Kernel

**What people do:** Put orchestration logic directly inside each specialist or domain package.
**Why it's wrong:** Every new workflow reinvents pause/resume, validation, and recovery.
**Do this instead:** Centralize lifecycle, approvals, and replay in `packages/orchestration`.

### Anti-Pattern 2: Side Effects Happen Inline with LLM Output

**What people do:** Use raw agent output to call external APIs immediately.
**Why it's wrong:** Replays and retries become unsafe, and approvals become unreliable.
**Do this instead:** Normalize, validate, persist, approve, then execute through adapters.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenAI | LLM provider through Helm's `packages/llm` boundary | Keep provider details out of kernel state transitions |
| Calendar system | Adapter with create/update block operations | Must be idempotent and linked to workflow sync records |
| Task system | Adapter with create/update task operations | Must support approval-gated writes and external IDs |
| Telegram | Operator command surface | Use for approval, revision, status, and replay-trigger interactions |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `apps/* ↔ packages/orchestration` | service calls / typed API | App layer triggers runs; package layer owns lifecycle |
| `packages/orchestration ↔ packages/agents` | typed specialist invocation | Kernel should not depend on domain-specific internals |
| `packages/orchestration ↔ packages/storage` | repositories / transactions | Persist after every major transition |
| `packages/orchestration ↔ packages/connectors` | adapter interface calls | All external writes should flow through this boundary |

## Sources

- LangGraph durable execution docs
- LangGraph interrupts and human-in-the-loop docs
- Helm V1 spec in `docs/internal/helm-v1.md`
- Existing repo architecture in `.planning/codebase/ARCHITECTURE.md`

---
*Architecture research for: durable orchestration kernel for Helm*
*Researched: 2026-03-11*

# Stack Research

**Domain:** Durable orchestration kernel for a personal AI workflow system
**Researched:** 2026-03-11
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11.x | Primary implementation language | Matches the existing repo, has strong async/server support, and keeps the kernel aligned with the current Helm runtime. |
| FastAPI | 0.128.x | Internal API surface for workflow control, inspection, approval, and replay endpoints | Remains the most pragmatic typed Python API framework for internal systems and already exists in the repo. |
| PostgreSQL | 17.x on current minor, or 18.x only if the hosting path is already ready | Durable system of record for workflow state, checkpoints, artifacts, approvals, and sync lineage | The kernel is DB-first by contract, and Postgres is the current durable foundation already used across Helm. |
| SQLAlchemy | 2.0.48 | ORM and transactional data access layer | Already established in the repo, mature for explicit transactions, and current 2.0 releases remain the stable line. |
| LangGraph | 1.0.x | Workflow graph execution, interrupts, and durable resume semantics | LangGraph 1.0 formalizes durable execution and human-in-the-loop patterns that match the kernel's core requirements. |
| OpenAI Responses API | current stable platform API | Structured agent/tool invocation layer for specialist agents | The Responses API is the current OpenAI agent primitive and supports structured outputs, tools, and background-style workflows. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Alembic | 1.14.x or current compatible release | Schema migrations for new workflow tables and artifact records | Use for every durable state change in `packages/storage` and workflow schema evolution. |
| Pydantic | 2.x | Typed request, artifact, and adapter payload schemas | Use for workflow contracts, approval payloads, agent outputs, and adapter-facing DTOs. |
| structlog | current repo-compatible release | Structured logs with workflow/run correlation | Use for every kernel transition, approval checkpoint, adapter write, and replay event. |
| python-telegram-bot | 22.2 | Telegram operator interaction surface | Use for approval/reject/revise commands and run inspection in the existing V1 UI. |
| psycopg | 3.x | PostgreSQL driver | Use as the default database driver behind SQLAlchemy. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Dependency and environment management | Already used by the repo; keep it as the single developer entry point. |
| Ruff | Linting and import hygiene | Fast, already adopted, and suitable for keeping orchestration modules explicit and boring. |
| Pytest | Unit and integration testing | Use for deterministic step tests, repository tests, restart/replay tests, and adapter contract tests. |
| Docker Compose | Local multi-service runtime | Keep it for Postgres-backed local validation of restart and resume behavior. |

## Installation

```bash
# Existing project stack remains the base
uv sync --extra dev

# If orchestration packages are added or updated
uv add langgraph "sqlalchemy>=2.0,<2.1" "psycopg[binary]>=3,<4"
uv add fastapi "pydantic>=2,<3" structlog
uv add python-telegram-bot
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| LangGraph 1.0.x | Temporal | Use Temporal only if Helm outgrows graph-level control and needs a heavier workflow control plane with stronger multi-worker scheduling guarantees. |
| SQLAlchemy 2.0.48 | SQLModel | Use SQLModel only if the repo decides to collapse ORM and API schemas together; current Helm is already SQLAlchemy-centric. |
| FastAPI 0.128.x | Litestar or Flask | Use alternatives only if FastAPI becomes a bottleneck, which is unlikely for this internal V1 control plane. |
| PostgreSQL 17.x | SQLite | Use SQLite only for hermetic tests; not for production workflow durability or concurrent resume/replay logic. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| In-memory workflow state | Breaks restart recovery, approval pause/resume, and replay inspection | Persist workflow state and artifacts in Postgres |
| Free-form agent outputs without schemas | Makes validation, replay, and adapter safety brittle | Use typed artifact schemas and structured outputs |
| Direct side effects from graph nodes without idempotency boundaries | Risks duplicate writes on retries or resume | Wrap side effects behind adapter tasks with persisted sync records |
| New workflow engines introduced only for this kernel | Adds migration and operational complexity to a repo that already has Python, Postgres, and LangGraph footing | Build the kernel on the existing stack first |

## Stack Patterns by Variant

**If staying close to the current repo:**
- Use FastAPI + worker + Telegram bot + Postgres + SQLAlchemy + LangGraph.
- Because this minimizes migration risk and turns the kernel into an architectural consolidation, not a rewrite.

**If LangGraph is used for durable steps:**
- Use a persistent Postgres-backed checkpointer and thread/run identifiers.
- Because interrupts, approvals, and resume semantics depend on persisted graph state.

**If some specialist logic remains non-graph-based at first:**
- Keep the kernel contract graph-friendly but allow step executors to call deterministic service functions.
- Because the immediate value is a durable run model, not forcing every specialist into one implementation style on day one.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.11.x | FastAPI 0.128.x | Matches the existing repo baseline and avoids unnecessary runtime churn. |
| SQLAlchemy 2.0.48 | psycopg 3.x | Stable current SQLAlchemy 2.0 line with modern PostgreSQL support. |
| LangGraph 1.0.x | OpenAI Responses API integration via Helm's LLM layer | Treat LangGraph as orchestration, not the provider SDK boundary. |
| python-telegram-bot 22.2 | Existing Telegram polling bot structure | Suitable for Telegram-first approvals in the current V1 model. |

## Sources

- LangGraph durable execution docs — durable execution, persistence, deterministic replay: https://docs.langchain.com/oss/python/langgraph/durable-execution
- LangGraph human-in-the-loop docs — interrupts, resume, approval/edit/reject semantics: https://docs.langchain.com/oss/python/langgraph/human-in-the-loop
- LangGraph 1.0 GA announcement — stable release positioning and durable-agent framing: https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available
- SQLAlchemy current docs — 2.0.48 current release line: https://docs.sqlalchemy.org/20/intro.html
- PostgreSQL versioning policy and current supported releases: https://www.postgresql.org/support/versioning/
- FastAPI official GitHub releases — current release cadence and latest stable tag: https://github.com/fastapi/fastapi
- OpenAI Responses API reference — structured outputs and tools direction: https://platform.openai.com/docs/api-reference/responses/list
- OpenAI agent tooling announcement — Responses API as the recommended foundation for agentic apps: https://openai.com/index/new-tools-for-building-agents/
- python-telegram-bot official releases — latest stable line: https://github.com/python-telegram-bot/python-telegram-bot/releases

---
*Stack research for: durable orchestration kernel for Helm*
*Researched: 2026-03-11*

# Feature Research

**Domain:** Durable orchestration kernel for a personal AI workflow system
**Researched:** 2026-03-11
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Durable workflow runs | A kernel is not credible if runs disappear on restart or crash | HIGH | Requires persisted run state, step pointers, and replay-safe semantics |
| Step-level artifact persistence | Users need inspectable lineage, not opaque prompt memory | MEDIUM | Persist raw input, normalized outputs, validation results, approvals, and summaries |
| Human approval checkpoints | High-impact side effects need explicit approval in this repo's V1 contract | MEDIUM | Must support approve, reject, and revise/resubmit paths |
| Specialist-agent dispatch | The kernel must call distinct specialists cleanly | MEDIUM | Invocation records, typed inputs/outputs, and failure isolation matter |
| Adapter-based external writes | Side effects need clean boundaries and auditable results | MEDIUM | Task/calendar integrations should look like adapters, not arbitrary service calls |
| Failure handling and recovery | Long-running workflows fail in practice | HIGH | Persist retryability, error details, and resumable state transitions |
| Inspectable run status | Operator must know where a workflow is paused or failing | LOW | Telegram/API status surfaces are enough for V1 |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Typed plug-in specialist contract | Makes new agents easy to add without bespoke orchestration code | MEDIUM | Strong leverage for future Helm domains |
| Approval-aware resume semantics | Turns approval from a bolt-on into a first-class workflow state | HIGH | Important for Telegram-driven human supervision |
| Full side-effect lineage | Makes adapter writes debuggable and trustworthy | MEDIUM | External object IDs and sync results should be linked to the originating run |
| Replayable representative workflow demo | Proves the kernel is real, not just abstractions | MEDIUM | Weekly task-to-calendar scheduling is the right V1 demo |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Fully autonomous outbound actions | Feels impressive and faster | Violates repo safety principles and makes failures costly | Keep explicit approval before meaningful writes |
| Generic multi-tenant workflow platform | Feels future-proof | Distracts from personal-internal V1 and creates abstraction debt | Stay single-user and artifact-driven |
| Dashboard-heavy control plane | Feels operationally complete | Adds UI scope before the kernel contract is stable | Keep Telegram/API inspection for V1 |
| Too many specialist agents at once | Feels modular | Creates surface area before the orchestration contract is validated | Start with `TaskAgent` and `CalendarAgent` only |

## Feature Dependencies

```text
Durable workflow runs
    └──requires──> persisted workflow state
                          └──requires──> workflow schema + repositories

Approval checkpoints
    └──requires──> interrupt/resume model
                          └──requires──> persisted decision records

Adapter-based external writes
    └──requires──> validated artifacts
                          └──requires──> typed specialist outputs

Failure recovery
    └──enhances──> durable workflow runs

Autonomous side effects
    ──conflicts──> explicit approval gates
```

### Dependency Notes

- **Durable workflow runs require persisted workflow state:** without a durable run model, restart recovery is fake.
- **Approval checkpoints require interrupt/resume plus decisions:** pause alone is not enough; the system must record who decided what and resume deterministically.
- **Adapter writes require validated artifacts:** external systems should consume normalized, inspectable outputs rather than raw model text.
- **Failure recovery enhances durable runs:** retries, replay, and partial recovery should all build on the same persisted execution model.
- **Autonomous side effects conflict with approval gates:** the V1 kernel should not optimize away the human checkpoint.

## MVP Definition

### Launch With (v1)

- [ ] Durable workflow run lifecycle — essential because the kernel exists to survive restarts and failures
- [ ] Typed specialist invocation for `TaskAgent` and `CalendarAgent` — essential to prove the plug-in model
- [ ] Persisted artifacts at each major step — essential for lineage, debugging, and downstream writes
- [ ] Approval checkpoint with approve/reject/revise behavior — essential for safe external side effects
- [ ] Adapter-backed writes with sync records and external IDs — essential to keep boundaries clean
- [ ] One representative end-to-end scheduling workflow — essential to validate the kernel with a real sequence

### Add After Validation (v1.x)

- [ ] Generic replay tooling improvements — add once the base lifecycle is stable
- [ ] Richer operator commands for workflow inspection/editing — add when day-to-day usage reveals the gaps
- [ ] More specialist agent types — add after the first two prove the contract

### Future Consideration (v2+)

- [ ] More autonomous workflow branches — defer until approval semantics and failure recovery are proven safe
- [ ] Multiple concurrent domain workflows sharing the same kernel — defer until the first workflow pattern stabilizes
- [ ] Additional user surfaces beyond Telegram — defer until the operator model hardens

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Durable run lifecycle | HIGH | HIGH | P1 |
| Specialist dispatch contract | HIGH | MEDIUM | P1 |
| Approval checkpoints | HIGH | MEDIUM | P1 |
| Persisted artifacts and lineage | HIGH | MEDIUM | P1 |
| Adapter sync records | HIGH | MEDIUM | P1 |
| Representative scheduling demo | HIGH | MEDIUM | P1 |
| Rich replay tooling | MEDIUM | MEDIUM | P2 |
| Additional specialist types | MEDIUM | MEDIUM | P2 |
| New operator UI surfaces | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Temporal-style systems | LangGraph-style systems | Our Approach |
|---------|------------------------|-------------------------|--------------|
| Durable execution | Strong workflow durability and replay | Built around graph persistence and interrupts | Use LangGraph-level durability with Helm-owned storage artifacts |
| Human approval | Usually custom application logic | First-class interrupt/resume support | Treat approval as a kernel state, not a one-off branch |
| Specialist tools/agents | Often activities/workers | Nodes, tasks, and tool-aware agents | Use typed specialist invocations with persisted artifacts |
| External side effects | Strong activity boundaries | Requires careful task/idempotency design | Put all side effects behind adapters plus sync records |

## Sources

- LangGraph durable execution docs
- LangGraph human-in-the-loop docs
- Helm product spec in `docs/internal/helm-v1.md`
- Existing Helm architecture map in `.planning/codebase/ARCHITECTURE.md`

---
*Feature research for: durable orchestration kernel for Helm*
*Researched: 2026-03-11*

# Pitfalls Research

**Domain:** Durable orchestration kernel for a personal AI workflow system
**Researched:** 2026-03-11
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Fake Durability

**What goes wrong:**
The workflow appears restart-safe in demos but actually loses step context, approval state, or side-effect lineage after a crash or deploy.

**Why it happens:**
Teams persist final artifacts but not intermediate step state, pending approvals, or retry metadata.

**How to avoid:**
Persist run state, step state, invocation records, approvals, artifacts, and sync records as first-class entities.

**Warning signs:**
Restart tests require manual repair, approval requests cannot be resumed deterministically, or operators rely on logs to reconstruct state.

**Phase to address:**
Phase 1: workflow lifecycle and persistence foundation

---

### Pitfall 2: Duplicate External Writes on Retry

**What goes wrong:**
Calendar blocks or downstream tasks are created twice when a worker restarts or a run is retried.

**Why it happens:**
Side effects are performed inline without idempotency keys or persisted sync history.

**How to avoid:**
Execute side effects through adapters that record attempt IDs, idempotency keys, external object IDs, and final outcomes.

**Warning signs:**
Retries re-run the same outbound call blindly or replay depends on "just don't click twice."

**Phase to address:**
Phase 3: adapter execution and approval-gated writes

---

### Pitfall 3: Kernel Logic Stays Trapped in Domain Agents

**What goes wrong:**
Each new workflow copies lifecycle logic, validation, pause/resume handling, and error policy from the last one.

**Why it happens:**
It feels faster to extend the currently working domain package than to extract a real orchestration boundary.

**How to avoid:**
Move run lifecycle, step contracts, approvals, and replay semantics into `packages/orchestration`, leaving specialists focused on their bounded job.

**Warning signs:**
Workflow state transitions live inside `email_agent`-style modules or app services instead of reusable orchestration code.

**Phase to address:**
Phase 2: orchestration boundary extraction

---

### Pitfall 4: Approval Is Only a UI Concept

**What goes wrong:**
The bot shows an approval prompt, but the underlying workflow has no persisted paused state or resumable decision record.

**Why it happens:**
Approval is implemented as a message flow instead of a kernel state transition.

**How to avoid:**
Model approvals as durable records tied to run ID, step ID, requested actions, allowed decisions, and resolution timestamps.

**Warning signs:**
Approvals disappear after restart, or the system cannot answer "what exactly was approved?"

**Phase to address:**
Phase 2: approval and resume semantics

---

### Pitfall 5: Agent Output Bleeds Into Adapters Unchecked

**What goes wrong:**
Raw model text or loosely shaped dicts drive scheduling and writes directly, causing brittle behavior and unsafe side effects.

**Why it happens:**
Schema discipline feels slower during early iteration.

**How to avoid:**
Require typed artifacts, explicit validation, and ambiguity flags before any downstream step or adapter executes.

**Warning signs:**
Adapters accept free-form payloads, or operator revisions require manually editing JSON in logs.

**Phase to address:**
Phase 1: typed workflow artifacts and validation

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reusing domain-specific tables for kernel state | Fast initial progress | Blurs ownership and makes future workflows harder to generalize | Acceptable only if wrapped by kernel repositories and migrated later |
| Storing approval context only in Telegram messages | Easy to ship | No durable lineage or safe restart recovery | Never acceptable for the kernel |
| Using ad hoc dict payloads between steps | Low friction | Validation drift and replay brittleness | Acceptable only in prototypes before schemas are locked |
| Hiding retry logic inside adapters | Simplifies the caller | Makes run-level recovery and observability inconsistent | Acceptable only for safe read-only calls |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Calendar adapter | Treating every retry as a fresh create | Use idempotency keys and reconcile external IDs |
| Task adapter | Mixing task normalization and external write logic | Separate normalized task artifacts from adapter-side mutation calls |
| Telegram approvals | Using message text as the source of truth | Persist approval requests and decisions in storage |
| LLM provider | Letting provider-specific response shapes leak into the kernel | Normalize provider outputs through typed Helm contracts |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Large unbounded artifact payloads | Slow reads and noisy status views | Persist concise normalized artifacts plus references to larger blobs if needed | Breaks once workflows accumulate many large artifacts |
| Poll-heavy approval loops | Worker churn and noisy logs | Separate paused runs from active execution scans | Breaks as paused runs accumulate |
| Overusing LLM calls for deterministic transforms | Higher latency and cost | Keep validation, state transitions, and adapter prep deterministic where possible | Breaks immediately on cost-sensitive repeated workflows |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging full sensitive workflow payloads | Exposes personal or external-system data | Log identifiers, summaries, and status transitions by default |
| Allowing adapter writes without approval state checks | Unsafe external side effects | Enforce approval prerequisites in the kernel, not just UI |
| Trusting agent-produced external IDs or commands blindly | Corrupt writes or unsafe mutations | Validate adapter-bound payloads against typed schemas and decision context |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Approval requests lack concrete diff/context | User cannot approve confidently | Show proposed writes, affected systems, and revision options |
| Run status is too vague | User cannot tell whether the workflow is safe to ignore | Expose current step, last result, and next required action |
| Failure states are opaque | User loses trust quickly | Persist clear failure reason plus next recovery option |

## "Looks Done But Isn't" Checklist

- [ ] **Workflow run:** Often missing restart recovery — verify a process restart can resume an in-flight paused run.
- [ ] **Approval gate:** Often missing revise/edit support — verify approve, reject, and revision paths are all persisted.
- [ ] **Adapter write:** Often missing idempotency — verify a retried run does not duplicate external objects.
- [ ] **Artifact lineage:** Often missing invocation linkage — verify every artifact links back to run and step metadata.
- [ ] **Replay support:** Often missing partial recovery — verify failed runs can be inspected and resumed or retried intentionally.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Fake durability | HIGH | Backfill run state tables, add restart tests, and reconcile orphaned artifacts |
| Duplicate writes | HIGH | Add sync reconciliation, idempotency keys, and duplicate detection against external IDs |
| Approval as UI-only | MEDIUM | Introduce durable approval records and convert UI actions into run-state transitions |
| Unchecked agent output | MEDIUM | Insert validation layer, ambiguity flags, and typed artifact schemas before adapters |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Fake durability | Phase 1 | Restart an interrupted run and confirm exact step resume |
| Unchecked agent output | Phase 1 | Validate structured artifacts and reject malformed outputs |
| Kernel logic trapped in domains | Phase 2 | New workflow steps consume shared orchestration contracts |
| Approval as UI-only | Phase 2 | Pause, approve, reject, and revise all survive restart |
| Duplicate external writes | Phase 3 | Retries and replay do not create duplicate downstream objects |

## Sources

- LangGraph durable execution docs
- LangGraph human-in-the-loop docs
- Helm V1 spec in `docs/internal/helm-v1.md`
- Existing repo architecture and concerns maps in `.planning/codebase/`

---
*Pitfalls research for: durable orchestration kernel for Helm*
*Researched: 2026-03-11*