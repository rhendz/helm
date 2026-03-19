"""Shared Google credential builder with automatic token refresh and DB write-back.

Security contract: access_token, refresh_token, and client_secret are NEVER logged.
Only user_id and expires_at appear in structured log events.
"""

from __future__ import annotations

from datetime import UTC

import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from helm_storage.models import UserCredentialsORM
from sqlalchemy.orm import Session

log = structlog.get_logger(__name__)


def build_google_credentials(
    user_id: int,
    creds: UserCredentialsORM,
    db: Session,
) -> Credentials:
    """Build a valid Google OAuth2 ``Credentials`` object from a ``UserCredentialsORM`` row.

    Handles the bootstrap case where ``access_token`` is ``None`` by triggering
    a refresh immediately.  On any successful refresh the new ``access_token`` and
    ``expires_at`` are written back to the ORM row and committed.

    Args:
        user_id: Internal user ID — used for logging only, never logged alongside secrets.
        creds: The ``UserCredentialsORM`` row for this user's Google provider.
        db: Active SQLAlchemy ``Session`` used for the write-back commit.

    Returns:
        A valid (non-expired) ``google.oauth2.credentials.Credentials`` instance.

    Raises:
        google.auth.exceptions.RefreshError: If token refresh fails (network error,
            revoked token, invalid client secret, etc.).
    """
    google_creds = Credentials(
        token=creds.access_token,
        refresh_token=creds.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds.client_id,
        client_secret=creds.client_secret,
    )

    # Refresh if the token is missing (bootstrap) or expired.
    if not google_creds.valid:
        try:
            google_creds.refresh(Request())
            # Write the new token back so future calls skip the refresh round-trip.
            creds.access_token = google_creds.token
            creds.expires_at = (
                google_creds.expiry.replace(tzinfo=UTC)
                if google_creds.expiry is not None
                else None
            )
            db.commit()
            log.info(
                "google_credentials_refreshed",
                user_id=user_id,
                expires_at=creds.expires_at.isoformat() if creds.expires_at is not None else None,
            )
        except Exception as exc:
            log.error(
                "google_credentials_refresh_failed",
                user_id=user_id,
                error=type(exc).__name__,
            )
            raise

    return google_creds
