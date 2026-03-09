# Domain Schema Owner Doc

Schema source: `docs/internal/helm-v1.md` section 10.

Current state:

- Minimal scaffold model exists in `packages/storage/src/helm_storage/models.py`.
- Full schema migration is pending.

Schema rules:

- Every workflow writes durable artifacts.
- Workflow transitions should be representable from stored state.
- New entities require migration + doc update.

TODO(v1-phase1): implement first Alembic migration and lock a baseline ERD.
