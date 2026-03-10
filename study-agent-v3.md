# Study Agent V3

## 1. V2 Reality Check

### What V2 actually implements

- Telegram-first command surface:
  - `/today`
  - `/start_session`
  - `/answer`
  - `/miss`
  - `/status`
  - `/checkin`
- Real solo-user identity plumbing:
  - the bot maps an actual Telegram user ID to one local user directory
  - still intentionally not multi-user infrastructure
- Explicit session lifecycle:
  - `recommended`
  - `in_progress`
  - `awaiting_answer`
  - `completed`
  - `abandoned`
  - `expired`
- Deterministic rules engine in `apps/study-agent/app/engine/rules.py`
- File-backed state with:
  - atomic writes
  - `.bak` backups
  - schema version fields
  - basic corruption fallback / recovery behavior
- Recent topic performance history
- Recommendation breakdowns with deterministic score components
- Weekly check-in with explicit proposed changes before apply

### What works well

- The app is materially more trustworthy than V1.
- Core state mutation is much less scattered.
- Session recovery is real now, not implied.
- Persistence is safer than the original overwrite-only model.
- Tests cover lifecycle, persistence, malformed model output, and check-in apply flow.
- Live verification against Telegram/OpenAI happened for the main flows.

### What is still shallow

- Recommendation quality is still a readable heuristic, not a strong learning planner.
- Course packs are still thin static files with weak sequencing metadata.
- Onboarding is still effectively “copy the seeded model.”
- Session structure is still one teach block, one quiz block, one answer block.
- Artifacts are readable but not structured enough to compound much value.

### What became more complex

- Session recovery and corrupted-state handling are now more defensive.
- Check-in logic is more honest, but also more stateful and harder to reason about casually.
- Recommendation explanations are more explicit, but still coupled to heuristic internals.
- There is now enough state that debugging by reading raw JSON will get harder over time.

### What still feels brittle

- Recommendation trust over repeated use.
  - The score breakdown is honest, but the actual heuristic is still rough.
- Check-in proposal extraction.
  - It is explicit now, but still built on local keyword matching.
- Longitudinal behavior.
  - The tests are stronger, but they still do not prove the system behaves well after weeks of use.
- Curriculum progression.
  - The app recommends topics, but it still does not manage progression in a way that feels intentional.

## 2. What V3 Should Optimize For

### 1. Recommendation trust over time

V2 can explain a recommendation, but that does not mean the recommendation is good. The next version should make “what should I study next?” feel correct across repeated days, not just plausible in one snapshot.

### 2. Better curriculum and onboarding structure

The app still depends on thin course packs and seeded state. V3 should make course setup less manual and progression less arbitrary without turning into a full curriculum platform.

### 3. Stronger retention signal with less guesswork

Recent history exists now, but the retention model is still coarse. V3 should improve how weak areas age, recover, and resurface.

### 4. Better transparency and debugging

As local state grows, the system will become harder to trust unless it gets easier to inspect why it did something and how a topic reached its current state.

## 3. Highest-Leverage Remaining Gaps

### Recommendation is still not trustworthy enough

The explanation is honest, but the policy is still shallow. It knows about due reviews, weak recent performance, miss pressure, and pacing, but it still has no real notion of:
- course progression
- backlog shape
- diminishing returns from repeating the same weak topic
- topic prerequisites
- when to move from recovery to advancement

### Course packs are too thin

The app can run on `course.md`, `topics.json`, `rubric.md`, and `sources.md`, but those files are still too minimal to support stronger recommendation quality. They do not encode enough about sequence, prerequisites, or topic importance.

### Onboarding is still weak

Real Telegram-user mapping exists, but real course onboarding still does not. New users or new courses still rely on copying the seeded shape rather than going through a clean setup flow.

### Check-in is honest but clunky

V2 improved honesty by separating proposals from apply, but the proposal generation still depends on brittle phrase matching and only supports a narrow class of edits.

### Artifacts are not compounding enough value

Session and weekly artifacts are readable, but mostly prose. They do not create enough structured residue to improve later recommendations, explainability, or course planning.

### Longitudinal testing is still thin

The current tests cover critical flows and hostile cases, but they still do not simulate a realistic multi-week usage pattern where bad heuristic drift becomes obvious.

## 4. Proposed V3 Features

### Product behavior improvements

#### Recommendation policy v2
- What: replace the current flat heuristic with a staged deterministic policy that distinguishes recovery, consolidation, and advancement.
- Why: the current model is honest but still not strong enough for repeated trust.
- Priority: core
- Complexity: medium

#### Explicit topic progression rules
- What: add simple prerequisite / next-topic / topic-group metadata to course packs and use it in prioritization.
- Why: the system currently treats topics too independently.
- Priority: core
- Complexity: medium

#### Recommendation audit output
- What: persist a compact recommendation audit artifact or JSON trace for each chosen session.
- Why: this makes debugging recommendation drift much easier.
- Priority: high-value
- Complexity: low

### Curriculum and onboarding improvements

#### Lightweight course onboarding flow
- What: a local-first onboarding path that creates a course state from a small metadata input and a topics file.
- Why: seeded files are not a real onboarding strategy.
- Priority: high-value
- Complexity: medium

#### Course-pack metadata expansion
- What: add fields like `priority_within_course`, `prerequisites`, `starter`, `review_weight`, `mode_preference`.
- Why: recommendation quality is bottlenecked by weak inputs.
- Priority: core
- Complexity: low

### Retention and state improvements

#### Better topic-memory model
- What: improve recent-history usage with simple notions of decay, repeated misses, recovery, and cooldown after over-reviewing.
- Why: current recent history exists, but does not yet drive enough high-quality retention behavior.
- Priority: core
- Complexity: medium

#### Structured artifact residue
- What: save compact structured fields alongside markdown artifacts, such as why the topic was chosen, what changed, and what should happen next.
- Why: prose artifacts alone do not compound enough value.
- Priority: high-value
- Complexity: medium

### UX and debug improvements

#### Explain state command or artifact
- What: add a small inspect/debug surface for why a topic is shaky, why a review is due, and why a recommendation was chosen.
- Why: trust degrades quickly if the system cannot explain its own state transitions.
- Priority: high-value
- Complexity: low

#### Smoother check-in proposal model
- What: keep deterministic application, but improve proposal extraction to avoid crude keyword behavior.
- Why: V2 is honest, but still awkward.
- Priority: high-value
- Complexity: medium

### Reliability and testing improvements

#### Longitudinal simulation tests
- What: deterministic multi-day / multi-week fixtures that exercise progression, misses, lite/full switching, and review resurfacing.
- Why: that is where the current bottleneck will show up.
- Priority: core
- Complexity: medium

## 5. Recommended V3 Scope

Keep V3 tight. Do not add dashboards, databases, or agent frameworks.

Recommended V3 slice:

1. Recommendation policy v2:
   - recovery vs consolidation vs advancement
   - better use of recent performance and miss recovery
2. Course-pack metadata expansion:
   - prerequisites
   - review weight
   - topic sequencing
3. Lightweight onboarding for new courses:
   - enough to create a real local course state without hand-editing seeded files
4. Longitudinal simulation tests and recommendation audit output

Why this is the highest leverage:
- V2’s next bottleneck is not safety anymore. It is trust in what the system recommends over time.
- Better policy without better metadata will underperform.
- Better metadata without a basic onboarding path will stay locked to seeded demos.
- Better behavior without longitudinal tests will regress silently.

## 6. Suggested Build Sequence

### Phase 1: Recommendation trust

1. Add course-pack metadata for sequencing and review weight.
2. Refactor prioritizer into clearer policy stages:
   - recovery
   - consolidation
   - advancement
3. Add recommendation audit output.

### Phase 2: Retention quality

1. Improve recent-history scoring with cooldown and repeated-failure handling.
2. Tighten review scheduling using those signals.
3. Validate lite/full behavior against the new policy.

### Phase 3: Onboarding

1. Add a lightweight local onboarding flow for new courses.
2. Generate initial course state from course metadata plus topic file.
3. Keep it file-backed and boring.

### Phase 4: Longitudinal verification

1. Add multi-day deterministic simulations.
2. Add golden tests for recommendation sequences.
3. Add regression fixtures for course progression and recovery loops.

## 7. Risks and Tradeoffs

### What should remain out of scope

- web UI
- database migration
- multi-user SaaS behavior
- vector retrieval
- autonomous curriculum rewriting
- background workers
- heavy analytics infrastructure

### Where complexity could balloon

- Recommendation policy can easily turn into a fake research-grade scheduler.
- Onboarding can balloon into a curriculum-generation product.
- Audit/debug features can turn into a dashboard if not kept local and minimal.

### What should stay deterministic

- recommendation policy
- topic progression rules
- review scheduling
- adherence accounting
- check-in mutation application
- onboarding state generation

### What can remain LLM-driven

- teaching
- quiz generation
- answer critique
- weekly summary drafting
- optional onboarding copy or course summary text

### Where trust could regress if V3 is done poorly

- If recommendation policy becomes more complex without becoming more inspectable.
- If course metadata becomes richer but inconsistent or hard to maintain.
- If onboarding adds too much magic and hides state assumptions.
- If artifacts stay prose-heavy while the policy becomes more advanced.

## 8. Acceptance Criteria for V3

- Recommendation behavior distinguishes recovery, consolidation, and advancement in a deterministic way.
- Course metadata includes enough sequencing information to influence recommendation order.
- Recommendation audit output makes it possible to explain why a topic was chosen and why mode was selected.
- A new course can be onboarded locally without hand-copying the seeded demo structure.
- Recent history affects not just pressure, but also cooldown and resurfacing behavior.
- Longitudinal simulation tests prove stable behavior over repeated days of use.
- V3 improves recommendation trust without adding infrastructure or hiding more logic in prompts.

## 9. Deferred / Nice-to-Have Ideas

- multi-message answer flow
- richer artifact exports
- explicit retry-now command
- session length recommendation
- course-pack authoring helpers
- structured run/debug CLI
- stronger check-in intent parsing beyond deterministic local rules
