# Connector Troubleshooting

Use this runbook for Gmail connector behavior and credential/auth failures in V1.

## Scope (V1 Today)

- Gmail connector exists as a normalization scaffold plus credential smoke script.

## 1) Fast Environment Checks

```bash
bash scripts/doctor.sh
```

Expected:

```text
doctor check passed
```

If `.env` is missing or tooling is unavailable, fix that first.

## 2) Gmail Credential/Auth Validation

Required env vars:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_USER_EMAIL`

Run the auth check:

```bash
uv run --frozen --extra dev python scripts/check-gmail-auth.py
```

Expected success:

```json
{"ok":true,"scope":"https://www.googleapis.com/auth/gmail.readonly","gmail_user_email":"<configured-email>","message_count_returned":<n>,"sample_message_ids":[...]}
```

Failure signatures:

- Missing env: `{"ok":false,"error":"missing_env",...}` (exit code 2)
- Gmail API/auth failure: `{"ok":false,"error":"gmail_http_error","status":...}` (exit code 1)
- Unexpected runtime failure: `{"ok":false,"error":"unexpected_error",...}` (exit code 1)

## 3) Connector Runtime Triage in Worker

Start or inspect worker logs:

```bash
docker compose up --build -d worker
docker compose logs --tail=150 worker
```

Expected V1 connector log patterns:

- Gmail scaffold with no manual payload: `gmail_pull_stub`
- Worker loop tick: `email_triage_job_tick`, `digest_job_tick`, `study_job_tick`

If `worker_job_failed` appears:

1. Capture `job` and `error` fields from the log line.
2. Check failed run records:

```bash
curl -sS "http://localhost:8000/v1/status/agent-runs/failures?limit=20"
```

3. Fix root cause (credentials/env/DB connectivity), then restart worker:

```bash
docker compose restart worker
```

## 4) Telegram Auth Guard (Operator Check)

Telegram command handlers reject unknown users using `TELEGRAM_ALLOWED_USER_ID`.

When misconfigured, bot replies:

```text
Unauthorized user.
```

Triage:

1. Verify `TELEGRAM_ALLOWED_USER_ID` in `.env`.
2. Restart bot:

```bash
docker compose restart telegram-bot
docker compose logs --tail=100 telegram-bot
```

3. Re-run a command (`/start`, `/actions`, `/drafts`) from the allowed account.

## 5) Normalization Failure Categories

Connector ingest paths record normalization failures by category while continuing
to process valid payloads.

Categories:

- Gmail: `missing_id`, `invalid_payload`

Where to inspect:

- Worker log event `email_triage_job_tick` includes `normalization_failures`.
## 6) Notes for Incident Triage

- For Gmail issues, the `check-gmail-auth.py` output is the fastest discriminator between env/config errors and upstream API errors.
