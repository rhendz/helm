"""ProviderFactory — returns typed providers for a given user session."""

from __future__ import annotations

from sqlalchemy.orm import Session

from helm_providers.gmail import GmailProvider
from helm_providers.google_calendar import GoogleCalendarProvider
from helm_providers.protocols import CalendarProvider, InboxProvider


class ProviderFactory:
    """Factory that resolves the correct provider implementation per user."""

    def __init__(self, user_id: int, db: Session) -> None:
        self._user_id = user_id
        self._db = db

    def calendar(self) -> CalendarProvider:
        """Return a ``GoogleCalendarProvider`` for the current user."""
        return GoogleCalendarProvider(self._user_id, self._db)

    def inbox(self) -> InboxProvider:
        """Return a ``GmailProvider`` for the current user."""
        return GmailProvider(self._user_id, self._db)
