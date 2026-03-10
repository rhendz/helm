# Study Agent MVP

Study Agent is a local, file-backed Telegram study bot. It recommends what to study, runs a teach-quiz-review loop with OpenAI, writes markdown artifacts, and updates JSON course state deterministically.

## What it includes

- Telegram bot using polling
- JSON-backed operational state
- Markdown prompts and study artifacts
- Deterministic prioritization, scheduling, and miss handling
- Seeded demo data for `system-design` and `thai-intro`

## Setup

1. Create a virtual environment with Python 3.11.
2. Install dependencies:

```bash
cd apps/study-agent
pip install -r requirements.txt
```

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

## Telegram commands

- `/today` shows the current recommendation
- `/start_session` starts the recommended teach-quiz-review loop
- `/answer <text>` submits the answer for the active session
- `/miss <reason>` records a missed session and increases scheduling pressure
- `/status` shows active courses, weak topics, adherence, and upcoming reviews
- `/checkin` starts the weekly check-in
- `/checkin <response>` answers the next weekly check-in question

## Repo structure

```text
apps/study-agent/
  README.md
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
- The app is single-user and maps Telegram interactions to `demo_user`.
- If the model returns malformed review JSON, the app falls back to a deterministic review result so the session can still complete.

## MVP limitations

- No onboarding wizard beyond seeded local files
- No database, web UI, Docker, or background workers
- No audio or pronunciation support
- One active study session per user
- One active weekly check-in per user
