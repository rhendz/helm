# Domain Schema Owner Doc

Schema source: `docs/internal/helm-v1.md` section 10.

Current state:

- SQLAlchemy V1 entities are implemented in `packages/storage/src/helm_storage/models.py`.
- Baseline schema revision is in `migrations/versions/20260308_0001_v1_baseline.py`.

Schema rules:

- Every workflow writes durable artifacts.
- Workflow transitions should be representable from stored state.
- New entities require migration + doc update.
