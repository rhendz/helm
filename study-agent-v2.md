# Study Agent V2

## 1. V1 Reality Check

### What V1 actually implements

- Telegram-first command surface with `/today`, `/start_session`, `/answer`, `/miss`, `/status`, and `/checkin`.
- Single-user local app under `apps/study-agent/`.
- File-backed state only:
  - course state in JSON
  - active session in `active_session.json`
  - active weekly check-in in `active_checkin.json`
  - session artifacts and weekly artifacts in markdown
- Seeded course packs for `system-design` and `thai-intro`.
- Deterministic recommendation logic with a simple weighted heuristic.
- LLM usage for:
  - teaching explanation
  - quiz generation
  - answer review
  - weekly check-in summary

### Implemented user flows

- Ask what to study today.
- Start the current recommended session.
- Submit one free-form answer for the active session.
- Record a miss with a reason.
- View a concise status snapshot.
- Run a four-question weekly check-in and write a weekly artifact.

### State management approach

- JSON is the operational source of truth.
- The app is effectively hard-wired to `demo_user`.
- Session state is a single active-session file.
- Check-in state is a single active-checkin file.
- File writes are direct overwrite operations with no atomic protection, no backup, and no migration path.

### Prompt architecture

- Prompt files are simple markdown templates.
- `teacher` and `quizzer` use plain text generation.
- `reviewer` uses structured outputs first, with normalization and fallback handling.
- `checkin` uses plain text summarization.

### What appears solid

- The basic vertical slice works end to end.
- Local-first storage is simple and understandable.
- The command surface is small and coherent.
- Session artifacts and weekly artifacts are readable and useful for V1.
- Review parsing is better than the earliest version because it now prefers structured outputs.
- Tests cover main command flows and some live verification has happened.

### What appears brittle

- The app is nominally Telegram-based, but the identity model is fake. It uses a real bot surface while mutating a hard-coded local user.
- Recommendation quality is shallow. The heuristic is readable, but it does not seriously model backlog, pacing, recovery after misses, or recent performance history.
- Session structure is thin. There is one teaching blob, one quiz blob, and one answer submission. There is no explicit lifecycle for resume, abandon, retry, or expiry.
- Review output is still LLM-dependent and normalized after the fact. The structured path is better, but trust still depends on shaping imperfect model output.
- Check-in state updates are crude string matching. A plausible summary can hide weak or overly broad state mutation.
- File persistence is fragile. There is no concurrency protection, no atomic write pattern, no backup, and no schema versioning.

### Known limitations

- No onboarding flow beyond seeded files.
- No true Telegram identity plumbing, even for a solo user.
- No session retry flow, partial completion flow, abandon flow, or stale-session recovery.
- No per-topic history beyond the latest aggregate state.
- No explanation of recommendation math beyond a short reason string.
- No clear semantics for `full` vs `lite` beyond prompt size.
- No robust handling of corrupted JSON or interrupted writes.

---

## 2. What V2 Should Optimize For

### 1. Resilient session execution

The session loop is the core product. If sessions become stale, ambiguous, or easy to corrupt, the agent stops feeling real. V2 should make sessions durable, explicit, and recoverable.

### 2. Trustworthy deterministic state updates

Mastery, confidence, adherence, review dates, and cadence changes should be updated by explicit rules, not scattered heuristics or ambiguous text interpretation.

### 3. Better recommendation quality

The product only earns trust if “what should I study now?” consistently feels right. V2 should improve recommendation quality using better local signals, not more model magic.

### 4. Better retention signal

V1 tracks weakness too coarsely. V2 should remember recent topic performance well enough to make review scheduling and prioritization more credible.

### 5. Keep the system local-first and boring

The next version should improve trust, correctness, and usability without introducing databases, dashboards, or agent infrastructure.

---

## 3. Highest-Leverage Gaps in V1

### Fake identity plumbing

This is a solo-user system pretending to be user-aware. The app should at least map the real Telegram user to a local profile instead of hard-coding `demo_user`.

### Weak session model

A session is effectively one teaching blob plus one quiz blob plus one answer blob. There is no explicit lifecycle, no stale-session recovery, no retry behavior, and no clear handling of abandoned work.

### Crude check-in state mutation

Weekly check-in writes a reasonable artifact, but the actual state mutation is primitive and easy to get wrong. The summary can sound intelligent while the JSON update is not.

### Thin recommendation model

Recommendation is deterministic, which is good, but it is too shallow. It does not use recent outcomes, miss recovery, lite/full bias, or course pacing in a meaningful way.

### Shallow persistence model

The files layer is simple but unsafe:
- direct overwrite writes
- no atomic temp-write-and-rename flow
- no backup snapshot
- no schema version
- no corruption recovery path

### Weak adherence semantics

Consistency is the primary product goal, but the app does not yet model:
- scheduled vs completed cleanly
- lite completion vs full completion
- abandoned sessions
- recovery after miss streaks

---

## 4. Proposed V2 Features

### Product behavior improvements

#### Real solo-user identity plumbing
- What: map the actual Telegram user ID to one local user profile instead of hard-coding `demo_user`.
- Why: this fixes the fake identity layer without turning the product into multi-user infrastructure.
- Priority: MVP-critical
- Complexity: low

#### Explicit session lifecycle
- What: add states for `recommended`, `in_progress`, `awaiting_answer`, `completed`, `abandoned`, and `expired`.
- Why: active-session handling is currently too easy to leave stale or ambiguous.
- Priority: MVP-critical
- Complexity: medium

#### Stale-session recovery flow
- What: when a session is stale, let the user explicitly `resume`, `abandon`, or `restart`.
- Why: recovery behavior is currently undefined and risks corrupting state.
- Priority: MVP-critical
- Complexity: medium

#### Recommendation breakdown
- What: return a structured breakdown of why something was chosen using real scoring inputs.
- Why: trust improves when the recommendation can explain itself without fake post-hoc storytelling.
- Priority: high-value
- Complexity: low

### State/model improvements

#### Deterministic rules engine
- What: centralize mastery, confidence, next-review, adherence, lite/full effects, miss pressure, and check-in mutations in one rules module.
- Why: V1 spreads core state changes across multiple places.
- Priority: MVP-critical
- Complexity: medium

#### Per-topic recent performance history
- What: store the last 3–5 outcomes for each topic, including date, mode, score band, and weak signals.
- Why: retention and recommendation quality need more than one floating-point mastery value.
- Priority: high-value
- Complexity: medium

#### Clear adherence model
- What: explicitly track scheduled sessions, full completions, lite completions, misses, abandons, and current miss streak.
- Why: consistency is the product’s primary objective and needs a cleaner model.
- Priority: MVP-critical
- Complexity: medium

#### Safer file writes and schema versioning
- What: atomic writes, optional `.bak` snapshots, and a `schema_version` field.
- Why: V1 is fragile for repeated long-term use.
- Priority: high-value
- Complexity: low

### Reliability and testing improvements

#### Golden-path progression tests
- What: add deterministic fixture-based tests for multi-day progression and recommendation behavior over time.
- Why: V1 mostly proves that commands run, not that the system behaves well across repeated use.
- Priority: high-value
- Complexity: medium

#### Structured-output contract tests
- What: test good reviewer outputs, malformed outputs, fallback paths, and normalization boundaries.
- Why: this is one of the most likely places for silent degradation.
- Priority: MVP-critical
- Complexity: low

#### Persistence safety tests
- What: test atomic writes, backup creation, schema version loading, and corrupted-state handling.
- Why: local-first trust depends on file safety.
- Priority: high-value
- Complexity: low

### UX improvements

#### Better answer flow
- What: support multi-message answers or a short retry path before finalizing review.
- Why: one-shot `/answer <text>` is brittle for real usage.
- Priority: high-value
- Complexity: medium

#### Explicit check-in proposals
- What: separate the weekly summary from the exact state changes that will be applied.
- Why: the system should not hide state mutation behind a smart-sounding paragraph.
- Priority: MVP-critical
- Complexity: medium

#### Stronger lite vs full behavior
- What: define when `lite` is recommended, how it affects adherence, and how it affects mastery/review scheduling.
- Why: lite mode is central to consistency but currently underspecified.
- Priority: MVP-critical
- Complexity: medium

### Content/course-pack improvements

#### Course-pack metadata upgrade
- What: add difficulty, recommended mode defaults, session length hints, starter sequencing, and canonical weak-signal labels.
- Why: current course packs are enough to run but too thin to support stronger recommendations.
- Priority: high-value
- Complexity: low

---

## 5. Recommended V2 Scope

Keep V2 tight. Do not expand into dashboards, databases, agent orchestration, or true multi-user architecture.

Recommended V2 slice:

1. Replace hard-coded `demo_user` with real solo-user Telegram identity plumbing.
2. Introduce an explicit session lifecycle with stale-session recovery.
3. Centralize all state mutations in one deterministic rules engine.
4. Add recent performance history and improve recommendation quality with a visible recommendation breakdown.
5. Harden persistence with atomic writes, backups, and schema versioning.
6. Make check-in mutations explicit before applying them.
7. Formalize adherence and lite/full semantics.

This is the highest-leverage slice because it makes the product more trustworthy without changing its fundamental local-first shape.

---

## 6. Suggested Build Sequence

### Phase 1: Correctness and trust

1. Add real solo-user Telegram identity plumbing.
2. Introduce `schema_version`, atomic writes, and backup snapshots.
3. Centralize all state transitions into one deterministic rules layer.

### Phase 2: Session hardening

1. Add explicit session lifecycle states.
2. Add stale active-session detection.
3. Add `resume`, `abandon`, and `restart` flows.
4. Ensure abandoned or expired sessions do not count as completed.

### Phase 3: Adherence and recommendation quality

1. Add explicit adherence semantics for full, lite, miss, and abandon.
2. Add recent performance history to topic state.
3. Improve recommendation heuristic using that history.
4. Expose recommendation score breakdown in `/today` and `/status`.

### Phase 4: Check-in honesty

1. Replace keyword-driven mutation with structured proposed changes.
2. Show exact changes before persisting them.
3. Persist approved changes through the deterministic rules layer.

### Phase 5: UX polish and tests

1. Improve answer flow with retry/multi-message support.
2. Add progression tests across several days of simulated usage.
3. Add contract tests for reviewer parsing and persistence safety.

---

## 7. Risks and Tradeoffs

### What should remain out of scope

- web UI
- database migration
- vector retrieval
- autonomous curriculum rewriting
- background workers
- broad plugin architecture
- true multi-user productization

### Where complexity could balloon

- Session recovery can turn into a full workflow engine if overdesigned.
- Recommendation logic can become fake spaced repetition if too clever.
- Check-in interpretation can drift into agentic planning instead of operational reprioritization.
- Onboarding can balloon into assessment and curriculum tooling.

### What should stay deterministic

- recommendation scoring
- session status transitions
- adherence accounting
- lite/full effects
- review scheduling
- cadence updates
- check-in state mutation

### What can remain LLM-driven

- teaching explanation
- quiz generation
- answer critique
- weekly summary drafting

The LLM should explain and critique. It should not directly mutate core study state.

---

## 8. Acceptance Criteria for V2

- The bot maps the real Telegram user to a local study profile without hard-coded `demo_user`.
- Sessions have explicit lifecycle states and can be resumed, abandoned, restarted, or expired safely.
- Stale active sessions are detected and resolved without corrupting adherence or topic state.
- Every state mutation path goes through one deterministic rules layer.
- `/today` includes a readable recommendation breakdown based on actual scoring inputs.
- Topic state preserves recent performance history and uses it in recommendation and review scheduling.
- Lite vs full mode has explicit effects on adherence, mastery updates, and review timing.
- Weekly check-in shows exactly which priorities, cadence fields, or topic states will change before applying them.
- File writes are atomic, versioned, and recover cleanly from interruption.
- Tests cover multi-step progression over time, not just single-command happy paths.

---

## 9. Nice-to-Haves / Deferred Ideas

- baseline assessment for new courses
- richer course-pack authoring format
- session length recommendation
- mini drill mode for weak-signal-only review
- explicit `retry same topic now` command
- simple export of artifacts and state snapshots
- lightweight CLI for local inspection and debugging