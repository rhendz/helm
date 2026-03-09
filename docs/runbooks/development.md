# Development Runbook

## First setup

```bash
cp .env.example .env
make bootstrap
make doctor
```

## Daily workflow

```bash
make format
make lint
make test
```

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
