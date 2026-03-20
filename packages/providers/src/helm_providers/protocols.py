"""Structural typing Protocols for calendar and inbox providers.

These Protocols use Python's structural (duck-typing) approach — concrete
provider classes do NOT inherit from these; they simply implement the same
method signatures and are compatible at type-check time.

``PullMessagesReport`` and ``GmailSendResult`` are forward references to types
defined in ``helm_providers.gmail`` (created in T03).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from zoneinfo import ZoneInfo

from helm_orchestration.schemas import (
    CalendarSyncRequest,
    CalendarSyncResult,
    SyncLookupRequest,
    SyncLookupResult,
)

if TYPE_CHECKING:
    from helm_providers.gmail import GmailSendResult, PullMessagesReport


class CalendarProvider(Protocol):
    """Structural interface for calendar integration providers."""

    def upsert_calendar_block(self, request: CalendarSyncRequest) -> CalendarSyncResult:
        """Create or update a time block in the external calendar system."""
        ...

    def reconcile_calendar_block(self, request: SyncLookupRequest) -> SyncLookupResult:
        """Look up whether a previously synced block still exists and matches."""
        ...

    def list_today_events(self, calendar_id: str, timezone: ZoneInfo) -> list[dict]:
        """Return today's calendar events for the given calendar and timezone."""
        ...

    def query_free_busy(
        self,
        calendar_id: str,
        start: "datetime",
        end: "datetime",
    ) -> list[tuple["datetime", "datetime"]]:
        """Return busy intervals within [start, end] as (start, end) UTC pairs."""
        ...


class InboxProvider(Protocol):
    """Structural interface for inbox (email) integration providers."""

    def pull_new_messages_report(
        self,
        manual_payload: list[dict] | None = None,
    ) -> PullMessagesReport:
        """Fetch and normalise new messages, returning a structured report."""
        ...

    def pull_changed_messages_report(
        self,
        *,
        last_history_cursor: str | None,
        manual_payload: list[dict] | None = None,
    ) -> PullMessagesReport:
        """Fetch messages changed since ``last_history_cursor``.

        Falls back to a full pull when ``last_history_cursor`` is ``None``
        (bootstrap case).
        """
        ...

    def send_reply(
        self,
        *,
        provider_thread_id: str,
        to_address: str,
        subject: str,
        body_text: str,
    ) -> GmailSendResult:
        """Send a reply within an existing provider thread."""
        ...
