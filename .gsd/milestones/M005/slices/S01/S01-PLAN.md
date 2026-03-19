# S01: Multi-User Identity Foundation

**Goal:** Full stack starts with a `users` row and `user_credentials` row seeded from `.env`; all domain ORM tables have a nullable `user_id` FK; `get_credentials(user_id, provider, db)` is available as a repository function for downstream slices.

**Demo:** After `alembic upgrade head` + bootstrap, `SELECT * FROM users` returns one row with the operator's Telegram ID and timezone; `SELECT * FROM user_credentials` returns one row with `provider='google'` and the operator's refresh token + email. All existing unit and integration tests still pass with the new nullable `user_id` columns.

## Must-Haves

- `UserORM` model with `id`, `telegram_user_id` (unique), `display_name`, `timezone`, timestamps
- `UserCredentialsORM` model with `user_id` FK, `provider`, `client_id`, `client_secret`, `refresh_token`, `access_token` (nullable), `expires_at` (nullable), `scopes`, `email`; unique constraint on `(user_id, provider)`
- Nullable `user_id` FK on all domain tables: `workflow_runs`, `email_threads`, `email_messages`, `email_drafts`, `email_send_attempts`, `action_proposals`, `classification_artifacts`, `draft_reasoning_artifacts`, `agent_runs`, `action_items`, `contacts`, `opportunities`, `replay_queue`, `email_deep_seed_queue`, `scheduled_thread_tasks`
- Schema-wipe Alembic migration chained after `20260317_0013`
- `bootstrap_user(db)` function: idempotent upsert of single user + Google credentials from env vars
- `run_bootstrap()` entry point wired into `scripts/migrate.sh` after `alembic upgrade head`
- `get_credentials(user_id, provider, db) -> UserCredentialsORM | None` repository function
- All new symbols exported from `helm_storage.repositories`
- Unit tests for bootstrap idempotency and `get_credentials`
- All existing tests still pass (nullable `user_id` columns, no NOT NULL violations)

## Proof Level

- This slice proves: operational (DB schema + startup bootstrap)
- Real runtime required: yes (Postgres for migration verification; SQLite for unit tests)
- Human/UAT required: no

## Verification

- `uv run --frozen --extra dev pytest tests/unit/test_user_bootstrap.py -v` — new tests pass
- `uv run --frozen --extra dev pytest tests/ -x --timeout=30` — full suite still passes (no regressions from nullable `user_id` FK)
- `scripts/lint.sh` passes
- `python -c "from helm_storage.models import UserORM, UserCredentialsORM; print('schema ok')"` — import succeeds (failure here means broken ORM class or missing `Base` registration)
- `uv run --frozen --extra dev pytest tests/ -x --timeout=30 -q 2>&1 | tail -20` — on failure, tail output shows the first failing test, error type, and traceback to enable rapid triage without re-running the full suite

## Observability / Diagnostics

- Runtime signals: `structlog` log `bootstrap_user_seeded` (user_id, telegram_user_id) on successful upsert; `bootstrap_user_skipped` warning when env vars missing
- Inspection surfaces: `SELECT * FROM users` and `SELECT * FROM user_credentials` in Postgres
- Failure visibility: bootstrap logs warning with missing env var name; does not crash
- Redaction constraints: `client_secret`, `refresh_token`, `access_token` must never appear in logs

## Integration Closure

- Upstream surfaces consumed: none (first slice)
- New wiring introduced: `run_bootstrap()` call added to `scripts/migrate.sh`; `UserORM` and `UserCredentialsORM` added to `models.py`; `get_credentials` exported from `helm_storage.repositories`
- What remains before the milestone is truly usable end-to-end: S02 (provider protocols + MCP wiring), S03–S06 (pipeline rewrites)

## Tasks

- [x] **T01: Add UserORM, UserCredentialsORM models and nullable user_id FK on domain tables** `est:45m`
  - Why: Every downstream slice depends on the `users` and `user_credentials` tables existing and domain tables having a `user_id` column. This is the schema foundation.
  - Files: `packages/storage/src/helm_storage/models.py`, `migrations/versions/20260318_0014_multiuser_identity.py`
  - Do: Add `UserORM` and `UserCredentialsORM` to `models.py`. Add nullable `user_id` FK (`ForeignKey("users.id", ondelete="SET NULL")`) to 15 domain tables. Create schema-wipe migration (0014) chained after 0013 that does `drop_all` + `create_all`. Do NOT add `user_id` to system/config tables (`job_controls`, `email_agent_configs`) or sub-tables scoped via parent FK (`workflow_steps`, `workflow_artifacts`, `workflow_events`, `workflow_approval_checkpoints`, `workflow_specialist_invocations`, `workflow_sync_records`, `draft_replies`, `draft_transition_audits`, `digest_items`).
  - Verify: `uv run --frozen --extra dev pytest tests/ -x --timeout=30` — all existing tests pass (SQLite `create_all` picks up new nullable columns without FK enforcement issues)
  - Done when: `UserORM` and `UserCredentialsORM` importable from `helm_storage.models`; migration file exists and chains after 0013; full test suite green

- [x] **T02: Implement bootstrap_user, get_credentials repository, exports, and migrate.sh wiring** `est:45m`
  - Why: The bootstrap function seeds the single operator user from env vars on every startup. The `get_credentials` repository function is the API that S02's providers will use to look up credentials. Both need to be exported from the storage package.
  - Files: `packages/storage/src/helm_storage/bootstrap.py`, `packages/storage/src/helm_storage/repositories/users.py`, `packages/storage/src/helm_storage/repositories/contracts.py`, `packages/storage/src/helm_storage/repositories/__init__.py`, `scripts/migrate.sh`
  - Do: (1) Create `bootstrap.py` with `bootstrap_user(db: Session)` that reads `TELEGRAM_ALLOWED_USER_ID`, `OPERATOR_TIMEZONE`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GMAIL_USER_EMAIL` from env. Upsert user by `telegram_user_id`, upsert credentials by `(user_id, provider="google")`. Skip silently with warning if `TELEGRAM_ALLOWED_USER_ID` is unset. Add `run_bootstrap()` that creates its own session. (2) Create `repositories/users.py` with `get_credentials(user_id, provider, db) -> UserCredentialsORM | None`. (3) Add `NewUser`, `NewUserCredentials` dataclasses to `contracts.py`. (4) Export new symbols from `__init__.py`. (5) Wire `run_bootstrap()` into `scripts/migrate.sh` after `alembic upgrade head`.
  - Verify: `python -c "from helm_storage.bootstrap import run_bootstrap; print('import ok')"` succeeds; `python -c "from helm_storage.repositories import get_credentials; print('export ok')"` succeeds
  - Done when: `bootstrap.py` and `repositories/users.py` exist with correct logic; `migrate.sh` calls `run_bootstrap()` after migration; all new symbols exported

- [x] **T03: Unit tests for bootstrap idempotency and get_credentials** `est:30m`
  - Why: Closes the verification loop — proves bootstrap is idempotent (safe to call on every startup), `get_credentials` returns correct results, and the full existing test suite has no regressions.
  - Files: `tests/unit/test_user_bootstrap.py`
  - Do: Write tests using SQLite in-memory engine + `Base.metadata.create_all()` pattern (matching existing test fixtures). Tests: (1) `test_bootstrap_creates_user_and_credentials` — sets env vars, calls `bootstrap_user(db)`, asserts user row exists with correct `telegram_user_id`/`timezone`, credentials row exists with correct `provider`/`email`/`refresh_token`. (2) `test_bootstrap_idempotent` — calls `bootstrap_user(db)` twice, asserts still exactly one user and one credentials row. (3) `test_bootstrap_skips_when_env_missing` — unsets `TELEGRAM_ALLOWED_USER_ID`, calls `bootstrap_user(db)`, asserts zero user rows (no crash). (4) `test_get_credentials_found` — seeds user + credentials, calls `get_credentials`, asserts returns correct ORM. (5) `test_get_credentials_not_found` — calls with wrong provider, asserts returns None.
  - Verify: `uv run --frozen --extra dev pytest tests/unit/test_user_bootstrap.py -v` and `uv run --frozen --extra dev pytest tests/ -x --timeout=30`
  - Done when: All 5 new tests pass; full test suite green; `scripts/lint.sh` passes

## Files Likely Touched

- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/bootstrap.py` (new)
- `packages/storage/src/helm_storage/repositories/users.py` (new)
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/__init__.py`
- `migrations/versions/20260318_0014_multiuser_identity.py` (new)
- `scripts/migrate.sh`
- `tests/unit/test_user_bootstrap.py` (new)
