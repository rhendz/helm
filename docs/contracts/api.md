# API Contract Scaffold

Base path: `/v1`

## Endpoints (Bootstrap)

- `GET /healthz`: liveness.
- `GET /v1/status`: coarse runtime status.
- `GET /v1/status/agent-runs/failures`: list recent failed agent runs for debug visibility.
- `GET /v1/actions`: list action items (placeholder).
- `GET /v1/drafts`: list drafts (placeholder).
- `POST /v1/study/ingest`: manual study ingest that extracts summary/tasks/gaps and persists `study_sessions`, `learning_tasks`, and `knowledge_gaps` when DB is available.
- `POST /v1/workflows/digest/run`: trigger digest generation with ranked artifact counts.

TODO(v1-phase2+): add schemas and behavior contract examples.
