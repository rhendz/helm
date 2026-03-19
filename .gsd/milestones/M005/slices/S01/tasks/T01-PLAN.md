---
estimated_steps: 5
estimated_files: 2
---

# T01: Add UserORM, UserCredentialsORM models and nullable user_id FK on domain tables

**Slice:** S01 — Multi-User Identity Foundation
**Milestone:** M005

## Description

Add the two new ORM models (`UserORM`, `UserCredentialsORM`) to `models.py` and add a nullable `user_id` foreign key column to 15 domain tables. Create a schema-wipe Alembic migration that drops and recreates all tables. This is the schema foundation that every subsequent slice in M005 depends on.

The critical constraint is that `user_id` must be **nullable** on all domain tables. Existing tests create ORM rows (e.g. `WorkflowRunORM`, `EmailThreadORM`) via SQLite in-memory with `Base.metadata.create_all()` and never seed a user. A NOT NULL `user_id` would break all ~80 of those test fixtures.

Tables that should NOT get `user_id`: system/config tables (`job_controls`, `email_agent_configs`) and sub-tables already scoped via parent FK chain (`workflow_steps`, `workflow_artifacts`, `workflow_events`, `workflow_approval_checkpoints`, `workflow_specialist_invocations`, `workflow_sync_records`, `draft_replies`, `draft_transition_audits`, `digest_items`).

## Steps

1. **Add `UserORM` to `models.py`** — Place it near the top of the file (before other models, since others will FK to it). Fields:
   - `id: Mapped[int]` — Integer, primary key, autoincrement
   - `telegram_user_id: Mapped[int]` — Integer, unique, nullable=False
   - `display_name: Mapped[str | None]` — String(255), nullable
   - `timezone: Mapped[str]` — String(64), nullable=False, default="UTC"
   - `created_at` / `updated_at` — same DateTime pattern as existing models
   - `__tablename__ = "users"`

2. **Add `UserCredentialsORM` to `models.py`** — Place right after `UserORM`. Fields:
   - `id: Mapped[int]` — Integer, primary key, autoincrement
   - `user_id: Mapped[int]` — ForeignKey("users.id", ondelete="CASCADE"), nullable=False
   - `provider: Mapped[str]` — String(32), nullable=False (e.g. "google")
   - `client_id: Mapped[str | None]` — String(255), nullable (OAuth app client ID)
   - `client_secret: Mapped[str | None]` — String(255), nullable (OAuth app client secret)
   - `access_token: Mapped[str | None]` — Text(), nullable (populated on first refresh)
   - `refresh_token: Mapped[str]` — Text(), nullable=False
   - `expires_at: Mapped[datetime | None]` — DateTime(timezone=True), nullable
   - `scopes: Mapped[str | None]` — Text(), nullable (comma-separated scope list)
   - `email: Mapped[str]` — String(320), nullable=False
   - `created_at` / `updated_at` — same pattern
   - `__table_args__` — `UniqueConstraint("user_id", "provider", name="uq_user_credentials_user_provider")`

3. **Add nullable `user_id` FK to 15 domain tables** — For each of these ORM classes, add:
   ```python
   user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
   ```
   Tables: `ContactORM`, `ActionItemORM`, `WorkflowRunORM`, `EmailMessageORM`, `EmailThreadORM`, `ActionProposalORM`, `ClassificationArtifactORM`, `EmailDraftORM`, `DraftReasoningArtifactORM`, `EmailSendAttemptORM`, `EmailDeepSeedQueueORM`, `ScheduledThreadTaskORM`, `AgentRunORM`, `OpportunityORM`, `ReplayQueueORM`.

4. **Create migration file `migrations/versions/20260318_0014_multiuser_identity.py`** — Follow the baseline migration pattern:
   ```python
   """multi-user identity foundation — schema wipe + recreate

   Revision ID: 20260318_0014
   Revises: 20260317_0013
   Create Date: 2026-03-18
   """
   from collections.abc import Sequence
   from helm_storage import models  # noqa: F401
   from helm_storage.db import Base

   revision: str = "20260318_0014"
   down_revision: str = "20260317_0013"
   branch_labels: str | Sequence[str] | None = None
   depends_on: str | Sequence[str] | None = None

   def upgrade() -> None:
       bind = op.get_bind()
       Base.metadata.drop_all(bind=bind)
       Base.metadata.create_all(bind=bind)

   def downgrade() -> None:
       bind = op.get_bind()
       Base.metadata.drop_all(bind=bind)
       Base.metadata.create_all(bind=bind)
   ```
   Add `from alembic import op` to imports.

5. **Run full test suite** to verify no regressions:
   ```bash
   uv run --frozen --extra dev pytest tests/ -x --timeout=30
   ```

## Must-Haves

- [ ] `UserORM` has `id`, `telegram_user_id` (unique), `display_name`, `timezone`, `created_at`, `updated_at`
- [ ] `UserCredentialsORM` has `user_id` FK, `provider`, `client_id`, `client_secret`, `refresh_token`, `access_token`, `expires_at`, `scopes`, `email`; unique constraint on `(user_id, provider)`
- [ ] 15 domain tables have nullable `user_id` FK with `ondelete="SET NULL"`
- [ ] Migration 0014 chains after 0013, does `drop_all` + `create_all`
- [ ] `job_controls` and `email_agent_configs` do NOT have `user_id`
- [ ] Sub-tables (`workflow_steps`, `workflow_artifacts`, etc.) do NOT have `user_id`
- [ ] All existing tests still pass

## Verification

- `uv run --frozen --extra dev pytest tests/ -x --timeout=30` — full suite passes
- `python -c "from helm_storage.models import UserORM, UserCredentialsORM; print('ok')"` — imports work

## Observability Impact

This task is schema-only (no runtime behavior), but leaves the following inspection surfaces:

- **Import smoke test:** `python -c "from helm_storage.models import UserORM, UserCredentialsORM; print('ok')"` — confirms ORM classes are registered with `Base.metadata`. If this fails, `Base.metadata.create_all()` calls in tests will silently omit the new tables.
- **SQLite create_all coverage:** `uv run --frozen --extra dev python -c "from sqlalchemy import create_engine; from helm_storage.db import Base; from helm_storage import models; e = create_engine('sqlite://'); Base.metadata.create_all(e); print([t for t in Base.metadata.tables])"` — lists all tables SQLAlchemy knows about after model import, verifying `users` and `user_credentials` appear.
- **Migration chain integrity:** If `down_revision` in `20260318_0014` is wrong, `alembic upgrade head` will fail with `Can't locate revision identified by ...`. The migration file stores the chain pointer as a module-level string constant, inspectable without running Alembic.
- **Test regression signal:** A NOT NULL `user_id` (violated constraint) would manifest as `IntegrityError: NOT NULL constraint failed: <table>.user_id` in any existing test that creates domain rows. This is immediately visible on `pytest -x --timeout=30` exit code 1.

## Inputs

- `packages/storage/src/helm_storage/models.py` — existing ORM models, all using `Mapped` + `mapped_column` pattern
- `packages/storage/src/helm_storage/db.py` — `Base` declarative base class
- `migrations/versions/20260317_0013_widen_payload_fingerprint.py` — previous migration (down_revision target)

## Expected Output

- `packages/storage/src/helm_storage/models.py` — updated with `UserORM`, `UserCredentialsORM`, and nullable `user_id` on 15 domain tables
- `migrations/versions/20260318_0014_multiuser_identity.py` — new schema-wipe migration
