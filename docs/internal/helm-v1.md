# Personal AI Secretary — V1 Spec

## 1\. Purpose

Build a personal AI leverage system that reduces dropped balls, reduces decision fatigue, and increases execution speed across three initial domains:

1. Opportunity / inbox triage  
     
2. Daily command briefing  
     
3. Study execution and weakness tracking

V1 is **not** a general consumer product.

V1 is a **personal internal system** designed to multiply my productivity and free time for higher-leverage work.

---

## 2\. Product Philosophy

This system should be:

- **Personal-first**, not generic-first  
    
- **Action-oriented**, not just informative  
    
- **Artifact-driven**, not chat-memory-driven  
    
- **Human-supervised** for important actions  
    
- **Modular**, so more agents can be added later  
    
- **Fast to iterate**, not overengineered

Core principle:

The system should create durable, reusable artifacts that other agents can consume, rather than hiding important state inside prompts or chat history.

---

## 3\. V1 Goals

### Primary goal

Create a working internal system that helps me:

- identify important inbound opportunities  
    
- draft responses faster  
    
- keep track of what needs action  
    
- receive a useful daily brief  
    
- maintain continuity in studying/interview prep

### Secondary goal

Create a clean enough codebase and workflow setup that multiple Codex agents can work in parallel on the project.

### Non-goal

V1 is **not** trying to solve:

- multi-tenant SaaS  
    
- public-facing productization  
    
- broad multi-channel support  
    
- full autonomous sending/posting  
    
- enterprise-grade control plane  
    
- dozens of agents at once

---

## 4\. V1 User

Single user: me.

All design decisions should optimize for:

- my workflows  
    
- my response style  
    
- my daily habits  
    
- my study/work cadence  
    
- my opportunity management needs

No abstraction should be added solely for hypothetical future users unless it clearly improves the internal system.

---

## 5\. Core V1 Workflows

## 5.1 Opportunity Inbox Triage

### Inputs

- Gmail messages  
- manually added items if needed

### Outputs

- classification  
    
- priority score  
    
- thread summary  
    
- action item  
    
- optional draft reply  
    
- digest item

### Success criteria

- important opportunities are surfaced quickly  
    
- low-value noise is filtered down  
    
- drafts exist for important replies  
    
- follow-ups do not get lost

---

## 5.2 Daily Command Briefing

### Inputs

- open action items  
    
- high-priority inbox/opportunity items  
    
- study tasks  
    
- optional calendar context later

### Outputs

- short daily digest sent through Telegram  
    
- clear recommended actions for the day

### Success criteria

- the briefing is concise and useful  
    
- it meaningfully helps decide what to do first  
    
- it is not overloaded with low-value information

---

## 5.3 Study Execution \+ Weakness Tracking

### Inputs

- manual study notes  
    
- mock interview notes  
    
- tutoring notes/transcripts  
    
- manually entered learning goals

### Outputs

- study summary  
    
- extracted learning tasks  
    
- knowledge gaps  
    
- review queue items  
    
- digest items when relevant

### Success criteria

- study tasks are captured consistently  
    
- weak areas accumulate into a durable record  
    
- the system can suggest next study priorities

---

## 5.4 Drafting \+ Approval Copilot

### Inputs

- important email threads  
    
- reply context  
    
- user rewrite instructions through Telegram

### Outputs

- stored draft replies  
    
- approval/snooze/edit flow through Telegram

### Success criteria

- replying is materially faster  
    
- important replies do not require starting from a blank page  
    
- user remains in control of final send decisions

---

## 6\. Core UX

## 6.1 Primary UI

Telegram is the primary UI for V1.

Telegram is used for:

- receiving notifications  
    
- viewing pending actions  
    
- viewing digest summaries  
    
- approving/snoozing drafts  
    
- requesting basic summaries/status

### Example commands

- `/digest`  
    
- `/drafts`  
    
- `/opportunities`  
    
- `/study`  
    
- `/actions`  
    
- `/approve <id>`  
    
- `/snooze <id>`

### Example interactions

- “show me today’s top 3 actions”  
    
- “show recruiter drafts”  
    
- “rewrite draft 12 warmer”  
    
- “what should I study tonight?”

---

## 7\. System Architecture

## 7.1 Architecture Style

Single-user modular monorepo.

Main pattern:

**connectors \-\> workflows/agents \-\> Postgres artifacts \-\> Telegram UI**

### Core rule

The source of truth is the database, not agent memory.

---

## 7.2 Main Components

### A. Connectors

Responsible for ingesting external data.

Initial connectors:

- Gmail  
    
- Telegram

### B. Agent / workflow layer

Responsible for:

- classification  
    
- summarization  
    
- extraction  
    
- drafting  
    
- digest generation

### C. Storage layer

Postgres stores durable artifacts and workflow state.

### D. API layer

Internal API used by:

- Telegram bot  
    
- admin/debug endpoints  
    
- manual triggers  
    
- approval endpoints

### E. Telegram bot

The main user-facing interface.

---

## 8\. Proposed Tech Stack

## 8.1 Backend

- Python 3.11+  
    
- FastAPI  
    
- SQLAlchemy  
    
- Alembic

## 8.2 Database

- Postgres

## 8.3 Agent orchestration

- LangGraph for stateful workflows, pauses, and approvals

## 8.4 UI

- Telegram bot (`python-telegram-bot`)

## 8.5 Local development

- Docker Compose

## 8.6 Scheduling

Initial:

- simple cron / APScheduler / lightweight scheduler in app

Future optional:

- Temporal if durable long-running workflows become necessary

## 8.7 LLM integration

Use OpenAI programmatically via the **Responses API** from the backend with an **API key**.

Use Codex separately for development and implementation acceleration. OpenAI’s current docs position Sign in with ChatGPT for Codex tooling, while app/back-end integration is documented via API key usage and the Responses API. :contentReference\[oaicite:1\]{index=1}

---

## 9\. Repo Strategy

Use **one monorepo** for V1.

### Target structure

personal-ai-secretary/

├─ README.md

├─ SPEC\_V1.md

├─ AGENTS.md

├─ .env.example

├─ docker-compose.yml

├─ apps/

│  ├─ api/

│  ├─ worker/

│  └─ telegram-bot/

├─ packages/

│  ├─ domain/

│  ├─ storage/

│  ├─ connectors/

│  ├─ agents/

│  │  ├─ email\_agent/

│  │  ├─ study\_agent/

│  │  └─ digest\_agent/

│  ├─ orchestration/

│  ├─ llm/

│  └─ observability/

├─ migrations/

├─ scripts/

├─ docs/

└─ tests/

---

## 10\. Domain Model

## 10.1 Shared Entities

### `contacts`

A normalized person record shared across channels.

Suggested fields:

* `id`  
* `name`  
* `email`  
* `telegram_handle`  
* `company`  
* `relationship_type`  
* `importance_score`  
* `created_at`  
* `updated_at`

### `action_items`

Track things that require action.

Suggested fields:

* `id`  
* `source_type`  
* `source_id`  
* `title`  
* `description`  
* `priority`  
* `status`  
* `due_at`  
* `created_at`  
* `updated_at`

### `draft_replies`

Drafts that can be approved, edited, or snoozed.

Suggested fields:

* `id`  
* `channel_type`  
* `thread_id`  
* `contact_id`  
* `draft_text`  
* `tone`  
* `status`  
* `created_at`  
* `updated_at`

### `digest_items`

Normalized items the daily digest can consume.

Suggested fields:

* `id`  
* `domain`  
* `title`  
* `summary`  
* `priority`  
* `related_contact_id`  
* `related_action_id`  
* `created_at`

### `agent_runs`

Track workflow execution for debugging and observability.

Suggested fields:

* `id`  
* `agent_name`  
* `source_type`  
* `source_id`  
* `status`  
* `started_at`  
* `completed_at`  
* `error_message`

---

## 10.2 Domain-Specific Entities

### Email

#### `email_messages`

* `id`  
* `provider_message_id`  
* `thread_id`  
* `from_address`  
* `subject`  
* `body_text`  
* `received_at`  
* `processed_at`

#### `email_threads`

* `id`  
* `latest_subject`  
* `thread_summary`  
* `category`  
* `priority_score`  
* `status`

#### `opportunities`

* `id`  
* `contact_id`  
* `company`  
* `role_title`  
* `channel_source`  
* `status`  
* `priority_score`  
* `notes`  
* `created_at`  
* `updated_at`

### Study

#### `study_sessions`

* `id`  
* `source_type`  
* `raw_text`  
* `summary`  
* `created_at`

#### `knowledge_gaps`

* `id`  
* `topic`  
* `description`  
* `severity`  
* `source_session_id`  
* `created_at`  
* `updated_at`

#### `learning_tasks`

* `id`  
* `title`  
* `description`  
* `priority`  
* `status`  
* `due_at`  
* `related_gap_id`

---

## 11\. Initial Agents

## 11.1 Email Agent

Responsibilities:

* ingest email  
* classify importance/category  
* summarize thread  
* create action items  
* generate draft replies for relevant threads  
* generate digest items for important cases

## 11.2 Study Agent

Responsibilities:

* summarize study inputs  
* extract learning tasks  
* detect knowledge gaps  
* generate digest items for important weaknesses

## 11.3 Digest Agent

Responsibilities:

* query shared artifacts  
* rank what matters today  
* build concise Telegram digest  
* avoid spam/noise

---

## 12\. Workflow Design

## 12.1 Email Triage Workflow

1. New email ingested  
2. Normalize/store raw message  
3. Classify email  
4. Update thread summary  
5. Create/update action item if needed  
6. Generate draft if needed  
7. Create digest item if needed  
8. Notify Telegram if high priority  
9. Log agent run

## 12.2 Study Ingest Workflow

1. Study note/transcript submitted  
2. Summarize session  
3. Extract learning tasks  
4. Detect knowledge gaps  
5. Add digest item if relevant  
6. Log agent run

## 12.4 Daily Digest Workflow

1. Gather open action items  
2. Gather highest-priority digest items  
3. Gather pending drafts  
4. Gather study priorities  
5. Generate concise briefing  
6. Send via Telegram  
7. Log agent run

---

## 13\. Human-in-the-Loop Rules

V1 should default to approval for meaningful outbound actions.

### Approval required

* sending important replies  
* posting/publishing content  
* deleting or archiving meaningful data  
* editing state in a destructive way

### Safe to automate without approval

* classification  
* summarization  
* internal artifact creation  
* draft generation  
* digest generation  
* reminders/notifications

---

## 14\. Non-Functional Requirements

### Reliability

* failed jobs should be visible  
* workflows should be retryable  
* agent runs should be logged

### Simplicity

* minimal infrastructure for v1  
* avoid premature microservices

### Observability

Need at least:

* structured logs  
* recent run status  
* error inspection  
* manual reprocessing for failed items

### Extensibility

The system should support adding future agents without redesigning the foundation.

Examples of future agents:

* content creation / blog pipeline  
* finance/admin agent  
* health/routine agent  
* calendar assistant  
* product/research agent

---

## 15\. Security / Privacy

This is a personal internal system, but it still handles sensitive information.

Requirements:

* secrets in environment variables or secure secret management  
* no credentials committed to repo  
* least privilege where practical  
* cautious logging to avoid dumping sensitive message bodies unnecessarily  
* maintain clear separation between dev/test/prod configs

---

## 16\. Testing Strategy

### Unit tests

* parsers  
* scoring logic  
* workflow branching logic  
* Telegram formatting/rendering

### Integration tests

* email triage end-to-end  
* digest generation end-to-end  
* approval flow end-to-end

### Manual test scripts

* reprocess a thread  
* seed fake recruiter messages  
* simulate daily digest  
* simulate study ingest

---

## 17\. Success Metrics for V1

V1 is successful if, within normal personal use:

1. Important inbound messages are surfaced reliably  
2. Draft replies materially reduce reply friction  
3. Daily brief is actually useful and concise  
4. Study tasks/knowledge gaps accumulate into usable continuity  
5. The system reduces mental load and improves follow-through  
6. The codebase is organized enough that multiple Codex agents can work in parallel

---

## 18\. Explicit V1 Non-Goals

Not in V1:

* multi-user auth  
* public SaaS deployment  
* polished admin dashboard  
* OpenClaw integration  
* full browser automation  
* fully autonomous outbound communication  
* broad app ecosystem support  
* advanced analytics UI  
* perfect generalized abstractions

---

## 19\. Build Phases

## Phase 1 — Foundation

* repo setup  
* DB schema  
* FastAPI skeleton  
* Telegram bot skeleton  
* OpenAI client wrapper  
* basic observability/logging  
* AGENTS.md for Codex instructions

## Phase 2 — Email loop

* Gmail ingestion  
* email triage workflow  
* draft generation  
* Telegram notifications  
* approval/snooze loop

## Phase 3 — Daily digest

* digest item generation  
* daily digest workflow  
* Telegram `/digest`

## Phase 4 — Study loop

* study input ingestion  
* task extraction  
* knowledge gap tracking  
* study summary query flow

## Phase 5 — Reliability, Operator Control, and Autonomy Acceleration

* reliability hardening across ingest/triage/digest/study flows  
* operator-safe reprocess controls and run visibility  
* deterministic idempotency and replay behavior  
* stronger digest ranking quality using multi-source artifact signals  
* night-runner execution reliability and Linear state consistency automation

---

## 20\. Codex Collaboration Plan

This repo should be prepared so multiple Codex agents can work in parallel.

### Required project artifacts

* `AGENTS.md`  
* clear repo layout  
* explicit contracts for each module  
* tickets scoped by boundary  
* one owner doc for system architecture  
* one owner doc for domain schema

### Initial parallel workstreams

1. repo/bootstrap \+ infra  
2. storage/domain models  
3. Telegram bot  
4. OpenAI client \+ prompt scaffolding  
5. email workflow  
6. digest workflow  
7. study workflow scaffolding  
8. tests/fixtures

---

## 21\. Open Questions

1. What is the exact Gmail ingestion method for V1?  
2. Should study ingest begin as manual text input only?  
3. Do we want simple admin endpoints in V1 for reprocessing/debugging?  
4. Do we want a minimal web dashboard in V1, or Telegram only?

Current recommendation:

* Telegram only for V1  
* no web dashboard yet  
* manual study ingest is acceptable initially

---

## 22\. Final V1 Decision Summary

V1 will be a:

* single-user  
* modular monorepo  
* Telegram-first  
* DB-first  
* human-supervised  
* agent-assisted personal leverage system

Its purpose is not to become a generalized assistant platform immediately.

Its purpose is to:

* protect opportunities  
* reduce cognitive overhead  
* improve execution consistency  
* create a foundation for future personal agents

A couple of refinements I’d make when you create the GitHub project:

First, set the runtime assumption in the repo to \*\*OpenAI API key \+ Responses API\*\*, while continuing to use \*\*Codex with ChatGPT sign-in\*\* for development workflows. That matches the current official docs much better than assuming your backend can run on ChatGPT OAuth alone. :contentReference\[oaicite:2\]{index=2}

If you want, next I’ll turn this into:

1\. an \`AGENTS.md\` for Codex, and  

2\. an initial set of parallelizable Linear tickets.

::contentReference\[oaicite:3\]{index=3}  

---

## 23\. V1 Expansion Execution Plan (Night Runner Ready)

This section defines the next V1 execution wave for autonomous implementation.
It is intentionally ticket-shaped so night-runner can process it with minimal interpretation.

### 23.1 Execution Policy For This Section

* process one issue at a time end-to-end (branch -> checks -> PR -> CI green -> merge -> sync main)  
* default checks for every issue:
  * `bash scripts/lint.sh`
  * `bash scripts/test.sh`
* if issue touches Docker/runtime startup, also run:
  * `bash scripts/compose-api-health-smoke.sh`
* do not mark done without merged PR URL and merge commit SHA recorded in Linear
* preserve Telegram-first and DB-first assumptions; no web dashboard expansion

### 23.2 Workstream A: Workflow Reliability Layer

Goal: make workflow execution deterministic and replay-safe.

#### A1. Add idempotency keys for ingest and triage writes

Acceptance criteria:

* each persisted artifact class used by workflows has a stable idempotency lookup path  
* repeated runs over the same source input do not duplicate durable artifacts  
* tests cover at-least-two-run behavior for each touched workflow

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

#### A2. Normalize agent run lifecycle states

Acceptance criteria:

* `agent_runs` follows a documented state path (`running`, `succeeded`, `failed`, optional replay marker)  
* every workflow trigger writes start + terminal state  
* failure paths include bounded error payloads and never crash status persistence

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

#### A3. Add replay/dead-letter model for failed units of work

Acceptance criteria:

* failed workflow payload references can be queued for replay  
* replay path uses existing contracts and writes a new run record  
* operator runbook documents replay trigger and rollback

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`
* `bash scripts/compose-api-health-smoke.sh`

### 23.3 Workstream B: Operator Control Plane (API-only)

Goal: allow controlled reprocessing and diagnostics without adding frontend scope.

#### B1. Reprocess endpoint set with explicit safety guards

Acceptance criteria:

* add bounded API endpoints for reprocessing by source id and/or time window  
* require explicit parameters (no broad unbounded replay)  
* include dry-run option returning affected counts without writes

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`
* `bash scripts/compose-api-health-smoke.sh`

#### B2. Workflow/job pause-resume controls

Acceptance criteria:

* operator can pause and resume scheduled job families (email/digest/study)  
* paused jobs emit explicit status in `/v1/status` family endpoints  
* worker respects pause state before executing job body

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

#### B3. Artifact traceability endpoint

Acceptance criteria:

* for action/draft/digest/opportunity entities, expose upstream source pointers and run id context  
* endpoint returns stable, redaction-safe debug payload  
* runbook includes “why did this exist?” debugging path

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

### 23.4 Workstream C: Digest Quality Upgrade

Goal: improve decision usefulness while staying deterministic and testable.

#### C1. Multi-source ranking policy formalization

Acceptance criteria:

* ranking policy combines existing digest items with action urgency and study signals  
* policy is deterministic and implemented in explicit code path (no hidden prompt-only ranking)  
* no-source fallback path remains stable and tested

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

#### C2. Reason-coded ranking output

Acceptance criteria:

* each ranked digest signal includes machine-readable reason tags (for example: urgency/freshness/source)  
* Telegram digest text uses concise human-readable rendering of top reasons  
* tests cover reason rendering contract

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

### 23.5 Workstream D: Triage Maturity

Goal: increase quality and confidence of triage artifacts.

#### D1. Stronger normalization + validation contracts

Acceptance criteria:

* connector normalization contracts reject malformed payloads with clear error categories  
* ingest paths record failure counts without breaking healthy message processing  
* fixtures cover malformed, partial, and valid payload mixes

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

#### D2. Duplicate detection and thread consolidation

Acceptance criteria:

* repeated provider events map to existing thread/message artifacts  
* triage outputs reuse existing open action/draft artifacts when source identity matches  
* regression tests cover duplicate and near-duplicate cases

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

### 23.6 Workstream E: Study Loop Expansion

Goal: make study artifacts more actionable in daily operations.

#### E1. Knowledge-gap dedupe and merge rules

Acceptance criteria:

* gap ingestion avoids duplicate open gaps for equivalent topics  
* updates severity/notes on existing gaps when appropriate  
* learning task linkage remains stable after dedupe

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

#### E2. Weekly study recap artifact generation

Acceptance criteria:

* create a recap artifact summarizing new gaps, resolved gaps, and top tasks  
* recap can be included as optional digest input  
* recap generation has deterministic tests

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

### 23.7 Workstream F: Approval and Outbound Safety Hardening

Goal: enforce human-supervised outbound rules consistently.

#### F1. Approval lifecycle audit trail

Acceptance criteria:

* every approval/snooze/terminal change is auditable by artifact id + timestamp  
* replay-safe handling prevents duplicate terminal transitions from repeated commands  
* failed approval actions produce visible operator signal

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

#### F2. Expiration and requeue behavior for pending drafts

Acceptance criteria:

* stale pending drafts can be flagged and optionally requeued/summarized  
* digest includes stale-approval visibility signal  
* tests cover expiration edge cases

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

### 23.8 Workstream G: Night Runner Reliability Automation

Goal: reduce coordination drift and failed unattended cycles.

#### G1. PR-to-Linear reconciliation automation

Acceptance criteria:

* merged PRs can be reconciled to Linear state with merge SHA evidence  
* unresolved state drift is surfaced in run report automatically  
* no issue is marked done without merged PR confirmation

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

#### G2. Auto-seeding next ready sprint items

Acceptance criteria:

* when sprint queue empties, night-runner seeds next ready issues from this section  
* created items include acceptance criteria and required validation commands  
* runner resumes execution without manual re-prompting unless blocked by human decision

Validation:

* `bash scripts/lint.sh`
* `bash scripts/test.sh`

### 23.9 Priority Order For Autonomous Execution

Use this order by default when generating/queuing issues:

1. Workstream A (reliability layer)  
2. Workstream B (operator control)  
3. Workstream C (digest quality)  
4. Workstream D (triage maturity)  
5. Workstream F (approval safety)  
6. Workstream E (study expansion)  
7. Workstream G (night-runner automation)

### 23.10 V1 Completion Gate (Updated)

V1 is complete when all conditions are true:

* core loops (email, digest, study, telegram action surface) are merged and stable  
* phase 6 reliability/operator priorities are completed or explicitly deferred with rationale  
* no unresolved high-priority open issues remain in active sprint  
* required CI checks are green on final merged set  
* runbooks reflect final supported operator workflows
