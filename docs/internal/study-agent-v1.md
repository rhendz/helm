# Study Agent MVP

## Goal

Build a **consistency-first study system** in **2 days** that works out of the box through **Telegram**.

The MVP should:
- reduce study friction
- keep the user accountable
- run a structured study loop
- track weak areas and review needs
- recommend what to study next
- support multiple courses with simple prioritization

This is **not** a full agent platform. It is a **file-backed workflow engine with LLM-assisted teaching, quizzing, and review**.

---

# Product Thesis

The MVP is valuable if it can do this reliably:

1. onboard a course
2. recommend what to study today
3. run a study session
4. review the user’s answers
5. update progress and weak areas
6. handle misses and rescheduling
7. perform a weekly recalibration

The system should feel like a **real study system**, not just a chat interface.

---

# Core Principles

## 1. Consistency first
Primary optimization target is showing up and completing sessions on schedule.

## 2. Retention second
The system should continuously resurface weak or aging material.

## 3. Real competence over fake progress
The agent should prefer recall, explanation, and application over passive exposure.

## 4. Low-friction startup
Starting a session must be extremely easy.

## 5. Deterministic workflow, not over-agentic autonomy
Use explicit app logic for state transitions and prioritization.
Use the LLM mainly for explanation, quiz generation, review, and artifact drafting.

---

# Non-Goals

Do **not** build these in MVP:

- multi-agent orchestration
- vector DB / advanced RAG
- audio/pronunciation grading
- rich UI beyond Telegram
- deep analytics dashboard
- advanced spaced repetition research system
- fully autonomous dynamic curriculum rewriting
- full source-grounded citation engine
- broad plugin/tool ecosystem

---

# User Experience

## Main entry point
Telegram

## Primary user actions
- ask what to study today
- start a session
- answer a quiz
- mark a miss
- run weekly check-in
- inspect weak areas / status

## Primary system outputs
- daily study recommendation
- structured study session
- reviewed feedback
- corrected mini notes
- weak areas
- next step
- updated course progress
- weekly recalibration summary

---

# MVP Features

## 1. Course Onboarding

The user provides:
- course name
- goal
- timeline or cadence preference
- current level
- weekly time or desired intensity
- optional sources

Examples:
- System Design Prep, target Senior SWE interviews in 3 months
- Intro Thai, ongoing casual study 3x/week

### Onboarding flow
1. collect course metadata
2. run baseline assessment
3. infer starting point
4. generate curriculum markdown
5. initialize course JSON state

### Output
- curriculum artifact in markdown
- initialized course state in JSON

---

## 2. Study Recommendation

The system recommends:
- which course to study
- which topic
- which mode (`full` or `lite`)
- suggested session length

### Recommendation inputs
- goal priority
- deadline pressure
- adherence
- review due topics
- weak areas
- how behind the user is
- cadence expectations

### Recommendation outputs
Example:
- Course: System Design
- Topic: Caching tradeoffs
- Mode: Lite
- Reason: You missed yesterday, this topic is due for review, and interview priority is higher than Thai this week.

---

## 3. Study Session Loop

A session is complete when it finishes a structured loop.

### Full session
1. Teach
2. Quiz
3. Review
4. Artifact generation
5. State update

### Lite session
A reduced version of the same loop:
1. Short teach
2. Smaller quiz
3. Review
4. Artifact generation
5. State update

### Session completion rule
A session only counts as completed if the predefined loop is completed.

---

## 4. Review + Feedback

Review mode should:
1. state what was correct
2. identify gaps
3. explain what a stronger answer would include
4. decide whether user should retry, review later, or move on

Review should be:
- blunt but useful
- structured
- tied to topic mastery updates
- uncertainty-aware when content is fuzzy

---

## 5. Weak Area Tracking

Track the highest-value memory only:
- topic state
- weak signals
- mastery estimate
- confidence signal
- review due date
- recent performance
- last seen date

The system should continuously update weak areas after sessions.

---

## 6. Miss Handling

When a session is missed:
1. flag it
2. ask why it was missed
3. reschedule
4. track miss history

If misses repeat:
- surface it explicitly
- bring it up during weekly check-in
- allow cadence adjustment

Tone:
- blunt
- not overly forgiving
- but still operational

---

## 7. Weekly Check-In

Purpose of weekly check-in, in priority order:
1. complaints
2. reprioritization
3. mastery correction
4. pace adjustment
5. missed-session review
6. confidence recalibration

The weekly check-in should allow the user to say things like:
- this feels too easy
- I’m behind on this course
- I know you marked this mastered but I still feel shaky
- this cadence is unrealistic
- prioritize interviews over Thai this week

### Output
- weekly markdown summary
- updated priorities / cadence / topic states in JSON

---

# System Architecture

## High-level approach

Build a:

**file-backed study workflow engine + Telegram bot + LLM prompt layer**

### Division of responsibility

#### Deterministic app logic
- course prioritization
- session state machine
- miss handling
- weekly escalation
- mastery bookkeeping
- review scheduling
- course state updates

#### LLM
- explain concept
- generate quiz
- review answer
- draft artifact
- help generate curriculum

---

# Data Model

## Rule
- **JSON = source of truth for operational state**
- **Markdown = human-facing artifacts and editable definitions**

---

# File Layout

```text
study-agent/
  prompts/
    system.md
    planner.md
    teacher.md
    quizzer.md
    reviewer.md
    checkin.md

  courses/
    system-design/
      course.md
      topics.json
      rubric.md
      sources.md
    thai-intro/
      course.md
      topics.json
      rubric.md
      sources.md

  data/
    users/
      ankush/
        profile.json
        active_courses.json
        course_state/
          system-design.json
          thai-intro.json
        sessions/
          2026-03-10-system-design.md
        weekly_reviews/
          2026-W11.md

  app/
    engine/
      onboarding.py
      prioritizer.py
      session_runner.py
      reviewer.py
      scheduler.py
      checkin.py
      artifact_writer.py
    schemas/
      course.py
      state.py
      session.py
    telegram/
      bot.py
````

---

# JSON Schemas

## User profile

```json
{
  "user_id": "ankush",
  "name": "Ankush",
  "preferences": {
    "tone": "blunt",
    "default_session_lengths": [20, 45, 90]
  }
}
```

## Active courses

```json
{
  "active_courses": [
    "system-design",
    "thai-intro"
  ]
}
```

## Course state

```json
{
  "course_id": "system-design",
  "title": "System Design Prep",
  "goal": "Senior SWE interviews in 3 months",
  "status": "active",
  "priority": 10,
  "cadence": {
    "target_sessions_per_week": 5,
    "recommended_mode_default": "full"
  },
  "adherence": {
    "scheduled": 8,
    "completed": 6,
    "missed": 2,
    "miss_streak": 1,
    "recent_miss_reasons": ["low energy", "schedule slip"]
  },
  "topics": [
    {
      "id": "caching-basics",
      "name": "Caching Basics",
      "state": "learning",
      "mastery": 0.42,
      "confidence": "shaky",
      "last_seen": "2026-03-10",
      "next_review": "2026-03-12",
      "weak_signals": [
        "cache invalidation",
        "write-through vs write-back"
      ]
    }
  ],
  "last_session_date": "2026-03-10",
  "weekly_checkin_needed": true
}
```

## Session record

```json
{
  "session_id": "2026-03-10-system-design-01",
  "course_id": "system-design",
  "topic_id": "caching-basics",
  "mode": "lite",
  "status": "completed",
  "started_at": "2026-03-10T09:00:00",
  "completed_at": "2026-03-10T09:18:00",
  "quiz_score": 0.65,
  "review_summary": "Understands why caching helps but weak on invalidation tradeoffs.",
  "weak_signals": [
    "cache invalidation",
    "write-through vs write-back"
  ],
  "next_step": "Retry caching tradeoffs in 2 days"
}
```

---

# Markdown Artifacts

## 1. Curriculum artifact

Generated during onboarding.

Contents:

* goal
* timeline / cadence
* baseline assessment summary
* proposed sequence of topics
* major milestones
* likely weak areas to watch
* study rhythm recommendation

## 2. Session artifact

Generated after each session.

Contents:

* topic covered
* corrected mini notes
* what you got right
* weak areas
* next step

## 3. Weekly check-in artifact

Generated after weekly recalibration.

Contents:

* adherence summary
* repeated misses or friction patterns
* user complaints / overrides
* reprioritization decisions
* mastery corrections
* cadence changes
* next week focus

---

# Telegram Commands

Keep the surface area tiny.

## Required commands

* `/today`
  Return recommended course, topic, mode, and reason.

* `/start_session`
  Start the recommended session.

* `/answer`
  Submit answer to the current quiz step.

* `/miss`
  Mark today’s session missed and capture reason.

* `/checkin`
  Run weekly recalibration flow.

* `/status`
  Show active courses, weak areas, misses, and next reviews.

## Optional later

* `/courses`
* `/weak_areas`
* `/reschedule`

---

# Core Engine Logic

## 1. Prioritization

Given all active courses, recommend one using:

* review urgency
* course goal priority
* deadline pressure
* adherence drift
* backlog / behindness
* cadence expectations

Simple weighted heuristic is enough for MVP.

---

## 2. Session state machine

```text
IDLE
  -> RECOMMENDED
  -> TEACHING
  -> QUIZZING
  -> REVIEWING
  -> ARTIFACT_WRITING
  -> COMPLETED
```

Miss path:

```text
RECOMMENDED
  -> MISSED
  -> RESCHEDULED
```

---

## 3. Mastery update

Keep this simple.

Mastery is influenced by:

* quiz/review performance
* recency
* user confidence signals
* whether explanation/application was weak

If user says “I still feel shaky” after strong performance:

* do not immediately override to weak
* trigger extra verification

---

## 4. Review scheduling

Keep simple rules, not fancy spaced repetition.

Example:

* weak topic: review in 1–2 days
* learning topic: review in 3–4 days
* solid topic: review in 7+ days

That is enough for MVP.

---

## 5. Miss escalation

Rules:

* one miss: flag + ask why + reschedule
* repeated misses: mention during check-in
* persistent misses: recommend cadence reduction or lite-mode bias

---

# Prompts

Use markdown prompt files.

## Required prompts

* `system.md`
  global behavior and tone

* `planner.md`
  curriculum generation and session recommendation framing

* `teacher.md`
  short explanation + immediate practice style

* `quizzer.md`
  recall/application-focused quiz generation

* `reviewer.md`
  evaluate answer, gaps, stronger answer, retry/move-on call

* `checkin.md`
  weekly recalibration flow

## Prompt design rule

Do not make these “agents” in an elaborate sense.
They are just reusable task prompts.

---

# Course Pack Design

Each course should plug into the same engine.

## Each course provides

* topics
* source material
* exercise style
* rubric
* mastery expectations

## Example course packs

### System Design Prep

* topics: caching, load balancing, databases, queues, consistency, scaling, etc.
* exercises: explain, compare tradeoffs, design prompts
* rubric: clarity, tradeoff quality, application, correctness
* mastery: explain + apply + justify

### Intro Thai

* topics: greetings, pronouns, sentence particles, common verbs, essential vocab
* exercises: translation, recall, short production
* rubric: correctness, recall strength, pattern use
* mastery: recall + produce basic forms reliably

---

# What Makes the MVP "Done"

The MVP is done when the following works end to end:

## Onboarding

* user can create a course
* baseline assessment runs
* curriculum artifact is generated
* course state JSON is initialized

## Daily workflow

* `/today` gives a recommendation
* `/start_session` runs teach -> quiz -> review
* session artifact is generated
* topic state updates correctly

## Miss workflow

* `/miss` flags and reschedules
* reason is captured
* repeated misses surface later

## Weekly workflow

* `/checkin` captures complaints, reprioritization, and mastery correction
* state is updated
* weekly artifact is generated

If that works, you have a real MVP.

---

# Day-by-Day Build Plan

## Day 1

### Focus

Single-course happy path

### Build

* repo structure
* JSON schemas
* one course pack
* onboarding flow
* curriculum generation
* `/today`
* `/start_session`
* teach -> quiz -> review
* session artifact generation

### End-of-day success

You can onboard one course and complete one session end to end.

---

## Day 2

### Focus

Operational usefulness

### Build

* multi-course prioritization
* `/miss`
* rescheduling logic
* adherence tracking
* `/status`
* weekly check-in
* weekly artifact generation
* second course pack

### End-of-day success

The system can manage multiple courses, handle misses, and recalibrate.

---

# Recommended Tech Choices

Keep it boring and fast.

* Python
* Telegram bot framework
* local JSON + markdown files
* Pydantic for schemas
* one LLM provider
* no DB for MVP

---

# Key Risks

## 1. Over-agentic design

Avoid freeform multi-agent complexity.

## 2. Markdown as mutable source of truth

Use JSON for state.

## 3. Too much onboarding complexity

Keep baseline assessment short.

## 4. Weak session completion semantics

Do not count partial chats as completed sessions.

## 5. Heavy startup flow

Make `/today` and `/start_session` extremely lightweight.

---

# Final Recommendation

Build this as a:

**consistency-first study workflow engine**
with:

* Telegram interface
* JSON-backed operational state
* markdown artifacts
* deterministic orchestration
* LLM-assisted teaching, quizzing, and review

That is the fastest path to something real in 2 days.