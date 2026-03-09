# Development Runbook

## First setup

```bash
cp .env.example .env
make bootstrap
```

## Daily workflow

```bash
make doctor
make lint
make test
```

## Run services

```bash
make up
```

- API: `http://localhost:8000`
- Postgres: `localhost:5432`

## Run apps directly

```bash
bash scripts/run-api.sh
bash scripts/run-worker.sh
bash scripts/run-telegram-bot.sh
```
