"""Bootstrap the single operator user from environment variables."""
import os

import structlog
from sqlalchemy.orm import Session

from helm_storage.db import SessionLocal
from helm_storage.models import UserCredentialsORM, UserORM

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
