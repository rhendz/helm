---
estimated_steps: 6
estimated_files: 5
---

# T02: Implement bootstrap_user, get_credentials repository, exports, and migrate.sh wiring

**Slice:** S01 — Multi-User Identity Foundation
**Milestone:** M005

## Description

Create the bootstrap function that seeds the single operator user + Google credentials from environment variables, the `get_credentials` repository function that downstream slices (S02+) use to look up credentials, wire the bootstrap into the migration script, and export all new symbols from the storage package.

The bootstrap must be **idempotent** — it runs on every container start via `migrate.sh`. It must also gracefully skip if required env vars are missing (common in CI and local dev without `.env`).

## Steps

1. **Create `packages/storage/src/helm_storage/bootstrap.py`** with:
   ```python
   """Bootstrap the single operator user from environment variables."""
   import os
   import structlog
   from sqlalchemy.orm import Session
   from helm_storage.db import SessionLocal
   from helm_storage.models import UserORM, UserCredentialsORM

   logger = structlog.get_logger()

   def bootstrap_user(db: Session) -> None:
       """Upsert the single bootstrap user and Google credentials from env vars.

       Idempotent: safe to call on every startup. Skips silently if
       TELEGRAM_ALLOWED_USER_ID is not set.
       """
       telegram_user_id_str = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()
       if not telegram_user_id_str:
           logger.warning("bootstrap_user_skipped", reason="TELEGRAM_ALLOWED_USER_ID not set")
           return

       telegram_user_id = int(telegram_user_id_str)
       timezone = os.environ.get("OPERATOR_TIMEZONE", "UTC")
       display_name = os.environ.get("OPERATOR_DISPLAY_NAME", "Operator")

       # Upsert user
       user = db.query(UserORM).filter(UserORM.telegram_user_id == telegram_user_id).first()
       if user is None:
           user = UserORM(
               telegram_user_id=telegram_user_id,
               display_name=display_name,
               timezone=timezone,
           )
           db.add(user)
           db.flush()  # get user.id

       # Upsert Google credentials (only if refresh token env var is set)
       refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
       gmail_email = os.environ.get("GMAIL_USER_EMAIL", "").strip()
       if refresh_token and gmail_email:
           cred = (
               db.query(UserCredentialsORM)
               .filter(
                   UserCredentialsORM.user_id == user.id,
                   UserCredentialsORM.provider == "google",
               )
               .first()
           )
           if cred is None:
               cred = UserCredentialsORM(
                   user_id=user.id,
                   provider="google",
                   client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
                   client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                   refresh_token=refresh_token,
                   email=gmail_email,
                   scopes="https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.modify",
               )
               db.add(cred)
           else:
               # Update mutable fields on re-run
               cred.client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
               cred.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
               cred.refresh_token = refresh_token
               cred.email = gmail_email

       db.commit()
       logger.info("bootstrap_user_seeded", user_id=user.id, telegram_user_id=telegram_user_id)


   def run_bootstrap() -> None:
       """Entry point for scripts/migrate.sh — opens its own session."""
       db = SessionLocal()
       try:
           bootstrap_user(db)
       finally:
           db.close()
   ```

   Key constraints:
   - `structlog` for logging (already a project dependency)
   - Skip with warning if `TELEGRAM_ALLOWED_USER_ID` is empty
   - Upsert user by `telegram_user_id`; upsert credentials by `(user_id, provider)`
   - On re-run, update `client_id`/`client_secret`/`refresh_token`/`email` (credentials may rotate)
   - Never log secret values — only log `user_id` and `telegram_user_id`

2. **Create `packages/storage/src/helm_storage/repositories/users.py`** with:
   ```python
   """User and credential repository functions."""
   from sqlalchemy.orm import Session
   from helm_storage.models import UserCredentialsORM, UserORM

   def get_credentials(user_id: int, provider: str, db: Session) -> UserCredentialsORM | None:
       """Look up credentials for a user + provider. Returns None if not found."""
       return (
           db.query(UserCredentialsORM)
           .filter(
               UserCredentialsORM.user_id == user_id,
               UserCredentialsORM.provider == provider,
           )
           .first()
       )

   def get_user_by_telegram_id(telegram_user_id: int, db: Session) -> UserORM | None:
       """Look up a user by their Telegram user ID. Returns None if not found."""
       return db.query(UserORM).filter(UserORM.telegram_user_id == telegram_user_id).first()
   ```

3. **Add dataclasses to `contracts.py`** — Add after the existing imports and dataclass definitions:
   ```python
   @dataclass(frozen=True)
   class NewUser:
       telegram_user_id: int
       timezone: str = "UTC"
       display_name: str | None = None

   @dataclass(frozen=True)
   class NewUserCredentials:
       user_id: int
       provider: str
       refresh_token: str
       email: str
       client_id: str | None = None
       client_secret: str | None = None
       scopes: str | None = None
   ```
   Also add `UserORM` and `UserCredentialsORM` to the imports from `helm_storage.models`.

4. **Update `repositories/__init__.py`** — Add imports and exports:
   - Import `get_credentials`, `get_user_by_telegram_id` from `.users`
   - Import `NewUser`, `NewUserCredentials` from `.contracts`
   - Add all four to `__all__`

5. **Wire `run_bootstrap()` into `scripts/migrate.sh`** — After the `alembic upgrade head` block, add:
   ```bash
   # Seed bootstrap user from env vars (idempotent)
   if command -v uv >/dev/null 2>&1; then
     uv run --frozen --extra dev python -c "from helm_storage.bootstrap import run_bootstrap; run_bootstrap()"
   else
     python -c "from helm_storage.bootstrap import run_bootstrap; run_bootstrap()"
   fi
   ```

6. **Verify imports work**:
   ```bash
   uv run --frozen --extra dev python -c "from helm_storage.bootstrap import run_bootstrap; print('bootstrap ok')"
   uv run --frozen --extra dev python -c "from helm_storage.repositories import get_credentials, get_user_by_telegram_id, NewUser, NewUserCredentials; print('exports ok')"
   ```

## Must-Haves

- [ ] `bootstrap_user(db)` upserts user by `telegram_user_id` and credentials by `(user_id, provider)`
- [ ] `bootstrap_user(db)` is idempotent — second call doesn't create duplicates or crash
- [ ] `bootstrap_user(db)` skips with structlog warning when `TELEGRAM_ALLOWED_USER_ID` is unset
- [ ] `bootstrap_user(db)` never logs secret values (`client_secret`, `refresh_token`, `access_token`)
- [ ] `get_credentials(user_id, provider, db)` returns `UserCredentialsORM | None`
- [ ] `get_user_by_telegram_id(telegram_user_id, db)` returns `UserORM | None`
- [ ] `run_bootstrap()` wired in `scripts/migrate.sh` after `alembic upgrade head`
- [ ] All new symbols exported from `helm_storage.repositories`

## Verification

- `uv run --frozen --extra dev python -c "from helm_storage.bootstrap import run_bootstrap; print('ok')"` — import succeeds
- `uv run --frozen --extra dev python -c "from helm_storage.repositories import get_credentials, NewUser, NewUserCredentials; print('ok')"` — exports work
- `grep 'run_bootstrap' scripts/migrate.sh` — returns match

## Observability Impact

- Signals added: `bootstrap_user_seeded` (info, user_id + telegram_user_id), `bootstrap_user_skipped` (warning, reason)
- How a future agent inspects this: check structlog output during `migrate.sh` execution
- Failure state exposed: missing env var name in warning log

## Inputs

- `packages/storage/src/helm_storage/models.py` — `UserORM` and `UserCredentialsORM` from T01
- `packages/storage/src/helm_storage/db.py` — `SessionLocal` for `run_bootstrap()`
- `packages/storage/src/helm_storage/repositories/contracts.py` — existing dataclass patterns
- `packages/storage/src/helm_storage/repositories/__init__.py` — existing export structure
- `scripts/migrate.sh` — existing migration script

## Expected Output

- `packages/storage/src/helm_storage/bootstrap.py` — new file with `bootstrap_user()` and `run_bootstrap()`
- `packages/storage/src/helm_storage/repositories/users.py` — new file with `get_credentials()` and `get_user_by_telegram_id()`
- `packages/storage/src/helm_storage/repositories/contracts.py` — updated with `NewUser`, `NewUserCredentials`
- `packages/storage/src/helm_storage/repositories/__init__.py` — updated with new exports
- `scripts/migrate.sh` — updated with `run_bootstrap()` call
