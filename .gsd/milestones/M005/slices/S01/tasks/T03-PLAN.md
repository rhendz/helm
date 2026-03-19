---
estimated_steps: 4
estimated_files: 1
---

# T03: Unit tests for bootstrap idempotency and get_credentials

**Slice:** S01 — Multi-User Identity Foundation
**Milestone:** M005

## Description

Write comprehensive unit tests that prove the bootstrap function is idempotent, `get_credentials` works correctly, and the full existing test suite has no regressions from the new nullable `user_id` columns. This closes the verification loop for S01.

Tests use SQLite in-memory engine with `Base.metadata.create_all()` — the same pattern used by all existing tests in this project (see `tests/unit/test_email_followup.py`, `tests/unit/test_email_triage_worker.py` for examples).

## Steps

1. **Create `tests/unit/test_user_bootstrap.py`** with 5+ tests:

   ```python
   """Tests for multi-user identity foundation (S01)."""
   import os
   from unittest.mock import patch

   import pytest
   from sqlalchemy import create_engine
   from sqlalchemy.orm import Session, sessionmaker

   from helm_storage.db import Base
   from helm_storage.models import UserORM, UserCredentialsORM
   from helm_storage.bootstrap import bootstrap_user
   from helm_storage.repositories.users import get_credentials, get_user_by_telegram_id
   ```

   Test setup: each test creates a fresh SQLite in-memory engine + session:
   ```python
   @pytest.fixture
   def db_session():
       engine = create_engine("sqlite://", echo=False)
       Base.metadata.create_all(engine)
       Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
       session = Session()
       yield session
       session.close()
   ```

   Tests to write:

   a. **`test_bootstrap_creates_user_and_credentials`** — Set env vars (`TELEGRAM_ALLOWED_USER_ID=12345`, `OPERATOR_TIMEZONE=America/New_York`, `GOOGLE_REFRESH_TOKEN=test-refresh`, `GMAIL_USER_EMAIL=test@example.com`, `GOOGLE_CLIENT_ID=cid`, `GOOGLE_CLIENT_SECRET=csec`), call `bootstrap_user(db)`, assert:
      - Exactly 1 `UserORM` row with `telegram_user_id=12345`, `timezone="America/New_York"`
      - Exactly 1 `UserCredentialsORM` row with `provider="google"`, `email="test@example.com"`, `refresh_token="test-refresh"`

   b. **`test_bootstrap_idempotent`** — Same env vars, call `bootstrap_user(db)` twice. Assert:
      - Still exactly 1 user row and 1 credentials row
      - No `IntegrityError` raised

   c. **`test_bootstrap_updates_credentials_on_rerun`** — Call bootstrap once with `GOOGLE_REFRESH_TOKEN=token-v1`, then change to `GOOGLE_REFRESH_TOKEN=token-v2` and call again. Assert credentials row has `refresh_token="token-v2"`.

   d. **`test_bootstrap_skips_when_telegram_id_missing`** — Unset `TELEGRAM_ALLOWED_USER_ID` (or set to empty string), call `bootstrap_user(db)`. Assert 0 user rows, no exception raised.

   e. **`test_bootstrap_skips_credentials_when_refresh_token_missing`** — Set `TELEGRAM_ALLOWED_USER_ID` but not `GOOGLE_REFRESH_TOKEN`. Assert user row created but 0 credentials rows.

   f. **`test_get_credentials_found`** — Seed a user + credentials manually, call `get_credentials(user.id, "google", db)`. Assert returns the correct `UserCredentialsORM`.

   g. **`test_get_credentials_not_found`** — Call `get_credentials(999, "google", db)`. Assert returns `None`.

   h. **`test_get_user_by_telegram_id`** — Seed a user, call `get_user_by_telegram_id(telegram_user_id, db)`. Assert returns correct user. Call with wrong ID, assert `None`.

   Use `monkeypatch.setenv` / `monkeypatch.delenv` for env var isolation (not `os.environ` directly).

2. **Run new tests**:
   ```bash
   uv run --frozen --extra dev pytest tests/unit/test_user_bootstrap.py -v
   ```

3. **Run full test suite** to confirm no regressions:
   ```bash
   uv run --frozen --extra dev pytest tests/ -x --timeout=30
   ```

4. **Run lint**:
   ```bash
   scripts/lint.sh
   ```

## Must-Haves

- [ ] At least 5 unit tests covering: create, idempotency, update-on-rerun, skip-when-missing, get_credentials found/not-found
- [ ] Tests use SQLite in-memory (no Postgres required)
- [ ] Tests use `monkeypatch` for env var isolation
- [ ] All new tests pass
- [ ] Full existing test suite still passes
- [ ] Lint passes

## Verification

- `uv run --frozen --extra dev pytest tests/unit/test_user_bootstrap.py -v` — all pass
- `uv run --frozen --extra dev pytest tests/ -x --timeout=30` — full suite green
- `scripts/lint.sh` — clean

## Inputs

- `packages/storage/src/helm_storage/models.py` — `UserORM`, `UserCredentialsORM` from T01
- `packages/storage/src/helm_storage/bootstrap.py` — `bootstrap_user()` from T02
- `packages/storage/src/helm_storage/repositories/users.py` — `get_credentials()`, `get_user_by_telegram_id()` from T02
- Existing test patterns: `tests/unit/test_email_followup.py` (SQLite fixture), `tests/unit/test_scheduled_thread_tasks.py` (create_all pattern)

## Expected Output

- `tests/unit/test_user_bootstrap.py` — new file with 5-8 passing tests
- All existing tests continue to pass (no regressions from nullable `user_id`)

## Observability Impact

**Signals added by this task:** None — this task adds only test code with no runtime effect.

**How to inspect:** All tests run via `uv run --frozen --extra dev pytest tests/unit/test_user_bootstrap.py -v`. Individual test names describe the signal path they exercise (e.g., `test_bootstrap_creates_user_and_credentials` confirms the `bootstrap_user_seeded` structlog path runs without error in isolation).

**Failure visibility:** A failing test surfaces the specific assertion and ORM state (row counts, field values) in pytest output. The most common failure modes are: `IntegrityError` (idempotency regression), `None` where a row is expected (env var not picked up), or `ImportError` (ORM not registered with Base.metadata).

**Redaction note:** Test env vars use dummy tokens (`test-refresh`, `csec`) — no real credentials appear in test output.
