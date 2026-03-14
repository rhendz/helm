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
