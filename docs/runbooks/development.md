# Development Runbook

## First setup

```bash
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

Optional:

```bash
uv run pre-commit install
```

## Daily workflow

```bash
bash scripts/format.sh
bash scripts/verify.sh
```

## Worktrees

For parallel Helm worktrees:

```bash
bash scripts/worktree-env.sh prepare
bash scripts/worktree-env.sh link-self
```

This shared `.venv` and `.env` flow is for Helm worktrees only. If study-agent or email-agent are extracted into their own repos, give them isolated environments and lockfiles instead of linking back to the Helm root.

## Run services

```bash
make up
```

`make up` runs `docker compose up --build`, which includes the `migrate` one-shot
service before long-running services start.

- API: `http://localhost:8000`
- Postgres: `localhost:5432`

## Run apps directly

```bash
bash scripts/run-api.sh
bash scripts/run-worker.sh
bash scripts/run-telegram-bot.sh
```

## Validation Notes

- Prefer the script entrypoints over ad hoc commands so local runs and CI stay aligned.
- When changing API, worker, or Telegram behavior, capture brief manual verification notes in the PR.
- CI is path-aware for pull requests, but `bash scripts/verify.sh` remains the default local pre-push check.
