# Study Agent V3

Study Agent is a local, file-backed Telegram study bot. It recommends what to study with a deterministic staged policy, runs a teach-quiz-review loop with OpenAI, writes markdown artifacts, and updates JSON course state through explicit rules.

## What it includes

- Telegram bot using polling
- JSON-backed operational state
- Markdown prompts and study artifacts
- Deterministic recommendation stages: `recovery`, `consolidation`, `advancement`
- Deterministic session lifecycle, scheduling, miss handling, and weekly check-in apply flow
- Recommendation audit traces for local debugging
- Lightweight local course onboarding
- Seeded demo data for `system-design` and `thai-intro`
- Real Telegram-user-backed solo-user identity mapping

## Setup

1. Create a virtual environment with Python 3.11.
2. Install dependencies:

```bash
cd apps/study-agent
uv sync
```

`requirements.txt` remains as a simple fallback, but `pyproject.toml` is now the preferred local and extraction-ready dependency contract.

3. Create a local env file:

```bash
cp .env.example .env
```

4. Set:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `OPENAI_MODEL` (optional, defaults to `gpt-5-mini`)

## Run locally

```bash
cd apps/study-agent
python -m app.main
```

The bot uses polling. Once it is running, talk to your bot in Telegram.

To create a new local course pack and initial course state without copying demo JSON by hand:

```bash
cd apps/study-agent
python -m app.onboarding \
  --user-id demo_user \
  --course-id new-course \
  --title "New Course" \
  --goal "Learn the new course steadily" \
  --topics-file /absolute/path/to/topics.json
```

## Telegram commands

- `/today` shows the current recommendation, policy stage, and audit breakdown
- `/start_session` starts, resumes, restarts, or abandons the current study loop
- `/answer <text>` submits the answer for the active session
- `/miss <reason>` records a missed session and increases scheduling pressure
- `/status` shows active courses, weak topics, adherence, upcoming reviews, and the current recommendation pressure
- `/checkin` starts the weekly check-in
- `/checkin <response>` answers the next weekly check-in question
- `/checkin apply` persists proposed weekly changes
- `/checkin cancel` discards proposed weekly changes

## Repo structure

```text
apps/study-agent/
  README.md
  pyproject.toml
  requirements.txt
  .env.example
  prompts/
  courses/
  data/
  app/
```

## Notes on behavior

- JSON is the operational source of truth.
- Markdown is used for prompts and output artifacts.
- The app is still optimized for one person, but it now maps the actual Telegram user ID to one local state directory.
- Session state is explicit and recoverable: `recommended`, `in_progress`, `awaiting_answer`, `completed`, `abandoned`, `expired`.
- Recommendation selection is policy-driven instead of flat scoring:
  - `recovery` stabilizes weak or missed material
  - `consolidation` reinforces partially learned material
  - `advancement` moves forward when prerequisites and recent behavior support it
- Course pack metadata is human-editable and affects sequencing:
  - `starter`
  - `prerequisites`
  - `next_topics`
  - `priority_within_course`
  - `review_weight`
  - `mode_preference`
- If the model returns malformed review output, the app falls back to a deterministic review result so the session can still complete.
- Persisted state files use schema versioning, atomic writes, and `.bak` backups.
- Recommendation decisions are written as compact JSON audit traces under each user directory.

## Current limitations

- Onboarding is still a local helper, not a conversational bot flow
- No database, web UI, Docker, or background workers
- No audio or pronunciation support
- One active study session per user
- One active weekly check-in per user
- Recommendation quality is stronger than V2 but still heuristic rather than research-grade scheduling
