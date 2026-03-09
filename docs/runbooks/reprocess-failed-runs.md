# Reprocess Failed Runs

Use this runbook when `agent_runs` show failures and you need to re-run with current V1 interfaces.

## Scope (V1 Today)

- Reprocessable through API: digest workflow (`POST /v1/workflows/digest/run`).
- Reprocessable through worker loop: `email_triage`, `digest`, `study` by restarting/rerunning worker jobs.
- No run-id replay endpoint exists yet.

## 1) Confirm a Failure Exists

Start services if needed:

```bash
docker compose up --build -d postgres api worker
```

Check API health and failed runs:

```bash
curl -sS http://localhost:8000/healthz
curl -sS "http://localhost:8000/v1/status/agent-runs/failures?limit=10"
```

Expected:

- `/healthz` returns JSON with `"status":"ok"`.
- Failures endpoint returns a JSON array. Failed rows include `"status":"failed"` and `error_message`.

## 2) Triage Before Reprocess

Inspect failing services:

```bash
docker compose logs --tail=150 api
docker compose logs --tail=150 worker
```

Common signals:

- DB/connectivity issue: API/worker errors followed by empty or stale status output.
- Runtime error in a job: worker log includes `worker_job_failed` with `job=<name>`.

Optional DB-level check:

```bash
docker compose exec postgres psql -U "${POSTGRES_USER:-helm}" -d "${POSTGRES_DB:-helm}" -c \
"select id, agent_name, source_type, status, started_at, completed_at, left(error_message, 160) as error from agent_runs order by id desc limit 20;"
```

Expected:

- Recent rows ordered by newest id.
- Failures have `status = failed` and a non-empty `error`.

## 3) Reprocess Digest Runs (API Path)

Trigger a fresh digest run:

```bash
curl -sS -X POST http://localhost:8000/v1/workflows/digest/run
```

Expected success payload:

```json
{"status":"ok","preview":"Daily Brief...","action_count":0,"digest_item_count":0,"pending_draft_count":0}
```

If execution fails, expected error payload:

```json
{"status":"error","preview":"Digest run failed.","action_count":0}
```

Validate failure count moves down or stops increasing:

```bash
curl -sS "http://localhost:8000/v1/status/agent-runs/failures?limit=10"
```

## 4) Reprocess Worker Jobs (Scheduler Path)

After fixing root cause (env/secrets/DB), restart worker:

```bash
docker compose restart worker
docker compose logs -f worker
```

Expected healthy loop signals:

- `worker_started` once on boot.
- Per poll: `email_triage_job_tick`, `digest_job_tick`, `study_job_tick`.
- No repeating `worker_job_failed`.

## 5) Closeout Checks

Run smoke validation:

```bash
bash scripts/smoke.sh
```

Expected:

- Lint and tests pass.
- `agent_runs` failures endpoint no longer growing for the same root cause.
