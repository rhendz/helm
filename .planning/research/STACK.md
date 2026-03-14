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
