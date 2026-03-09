# Domain Schema Owner Doc

Schema source: `docs/internal/helm-v1.md` section 10.

Current state:

- V1 entities from `docs/internal/helm-v1.md` section 10 are defined in
  `packages/storage/src/helm_storage/models.py`.
- Baseline Alembic migration exists at
  `migrations/versions/20260308_0001_rhe12_rhe13_baseline.py`.
- Repository contracts + SQLAlchemy implementations are available for:
  - `action_items`
  - `draft_replies`
  - `digest_items`

Schema rules:

- Every workflow writes durable artifacts.
- Workflow transitions should be representable from stored state.
- New entities require migration + doc update.
