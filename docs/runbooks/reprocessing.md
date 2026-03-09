# Reprocessing

Use this when a failed workflow run should be retried.

## Current V1 scaffold path

1. Check recent failed runs:
   `GET /v1/admin/agent-runs?status=failed&limit=20`
2. Retry an eligible failed run:
   `POST /v1/admin/agent-runs/{run_id}/reprocess`
3. Confirm retry execution via:
   `GET /v1/admin/agent-runs?limit=20`

## Notes

- V1 currently supports direct reprocess for `digest_workflow` failures.
- Non-digest reprocess handlers are scaffolded but not yet implemented.
