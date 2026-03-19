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
