# Failure Triage (RHE-20)

Use this when workflows fail or appear stuck.

## 1. Check runtime status

```bash
curl -s http://localhost:8000/v1/status
```

Key fields:

- `state`: `degraded` indicates recent failures or unavailable run storage.
- `runs.failed_count`: number of failed runs in the recent window.
- `runs.latest_failure`: most recent failure summary (`agent_name`, `source_type`, `error_message`).

## 2. Inspect recent run history

```bash
curl -s "http://localhost:8000/v1/admin/agent-runs?limit=20"
curl -s "http://localhost:8000/v1/admin/agent-runs?status=failed&limit=20"
```

Use this to confirm if failures are isolated or continuous.

## 3. Reprocess a failed run (scaffold)

```bash
curl -s -X POST "http://localhost:8000/v1/admin/agent-runs/<RUN_ID>/reprocess"
```

Current V1 behavior:

- `digest_workflow` failed runs can be retried directly.
- other workflow types return `not_supported` until dedicated handlers are added.

## 4. Validate retry result

1. Recheck `GET /v1/status`.
2. Recheck `GET /v1/admin/agent-runs?limit=20`.
3. Confirm a new run exists with `source_type=reprocess` and `status=success` (or inspect new failure).
