"""Tests for multi-user identity foundation (S01).

Covers: bootstrap idempotency, credential upsert, skip-when-missing paths,
and get_credentials / get_user_by_telegram_id repository functions.
All tests use SQLite in-memory — no Postgres required.
"""

import pytest
from helm_storage.bootstrap import bootstrap_user
from helm_storage.db import Base
from helm_storage.models import UserCredentialsORM, UserORM
from helm_storage.repositories.users import get_credentials, get_user_by_telegram_id
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_ENV = {
    "TELEGRAM_ALLOWED_USER_ID": "12345",
    "OPERATOR_TIMEZONE": "America/New_York",
    "GOOGLE_REFRESH_TOKEN": "test-refresh",
    "GMAIL_USER_EMAIL": "test@example.com",
    "GOOGLE_CLIENT_ID": "cid",
    "GOOGLE_CLIENT_SECRET": "csec",
}


def _seed_user(session: Session, telegram_user_id: int = 99) -> UserORM:
    user = UserORM(telegram_user_id=telegram_user_id, display_name="Tester", timezone="UTC")
    session.add(user)
    session.flush()
    return user


def _seed_credentials(session: Session, user_id: int) -> UserCredentialsORM:
    cred = UserCredentialsORM(
        user_id=user_id,
        provider="google",
        refresh_token="seed-refresh",
        email="seed@example.com",
    )
    session.add(cred)
    session.flush()
    return cred


# ---------------------------------------------------------------------------
# bootstrap_user tests
# ---------------------------------------------------------------------------


def test_bootstrap_creates_user_and_credentials(monkeypatch, db_session):
    """Bootstrap creates exactly one user and one credentials row with correct values."""
    for k, v in _BASE_ENV.items():
        monkeypatch.setenv(k, v)

    bootstrap_user(db_session)

    users = db_session.query(UserORM).all()
    assert len(users) == 1
    assert users[0].telegram_user_id == 12345
    assert users[0].timezone == "America/New_York"

    creds = db_session.query(UserCredentialsORM).all()
    assert len(creds) == 1
    assert creds[0].provider == "google"
    assert creds[0].email == "test@example.com"
    assert creds[0].refresh_token == "test-refresh"


def test_bootstrap_idempotent(monkeypatch, db_session):
    """Calling bootstrap_user twice does not duplicate rows or raise IntegrityError."""
    for k, v in _BASE_ENV.items():
        monkeypatch.setenv(k, v)

    bootstrap_user(db_session)
    bootstrap_user(db_session)  # second call must be safe

    assert db_session.query(UserORM).count() == 1
    assert db_session.query(UserCredentialsORM).count() == 1


def test_bootstrap_updates_credentials_on_rerun(monkeypatch, db_session):
    """Re-running bootstrap with a new refresh token updates the existing credentials row."""
    for k, v in _BASE_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "token-v1")
    bootstrap_user(db_session)

    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "token-v2")
    bootstrap_user(db_session)

    creds = db_session.query(UserCredentialsORM).all()
    assert len(creds) == 1
    assert creds[0].refresh_token == "token-v2"


def test_bootstrap_skips_when_telegram_id_missing(monkeypatch, db_session):
    """Bootstrap silently skips when TELEGRAM_ALLOWED_USER_ID is not set."""
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_ID", raising=False)

    bootstrap_user(db_session)  # must not raise

    assert db_session.query(UserORM).count() == 0


def test_bootstrap_skips_when_telegram_id_empty_string(monkeypatch, db_session):
    """Bootstrap silently skips when TELEGRAM_ALLOWED_USER_ID is set to empty string."""
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "")

    bootstrap_user(db_session)

    assert db_session.query(UserORM).count() == 0


def test_bootstrap_skips_credentials_when_refresh_token_missing(monkeypatch, db_session):
    """Bootstrap creates a user row but skips credentials when GOOGLE_REFRESH_TOKEN is unset."""
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "12345")
    monkeypatch.setenv("OPERATOR_TIMEZONE", "UTC")
    monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("GMAIL_USER_EMAIL", raising=False)

    bootstrap_user(db_session)

    assert db_session.query(UserORM).count() == 1
    assert db_session.query(UserCredentialsORM).count() == 0


# ---------------------------------------------------------------------------
# Repository function tests
# ---------------------------------------------------------------------------


def test_get_credentials_found(db_session):
    """get_credentials returns the correct row when it exists."""
    user = _seed_user(db_session)
    cred = _seed_credentials(db_session, user.id)
    db_session.commit()

    result = get_credentials(user.id, "google", db_session)

    assert result is not None
    assert result.id == cred.id
    assert result.refresh_token == "seed-refresh"
    assert result.email == "seed@example.com"


def test_get_credentials_not_found(db_session):
    """get_credentials returns None when no matching row exists."""
    result = get_credentials(999, "google", db_session)
    assert result is None


def test_get_credentials_wrong_provider(db_session):
    """get_credentials returns None when the provider does not match."""
    user = _seed_user(db_session)
    _seed_credentials(db_session, user.id)
    db_session.commit()

    result = get_credentials(user.id, "github", db_session)
    assert result is None


def test_get_user_by_telegram_id(db_session):
    """get_user_by_telegram_id returns correct user or None."""
    user = _seed_user(db_session, telegram_user_id=77777)
    db_session.commit()

    found = get_user_by_telegram_id(77777, db_session)
    assert found is not None
    assert found.id == user.id
    assert found.telegram_user_id == 77777

    missing = get_user_by_telegram_id(00000, db_session)
    assert missing is None
