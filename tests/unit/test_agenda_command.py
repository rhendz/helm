"""Unit tests for the /agenda Telegram command handler."""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from helm_telegram_bot.commands import agenda


class _Message:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _Update:
    def __init__(self, *, user_id: int = 1) -> None:
        self.message = _Message()
        self.effective_user = type("User", (), {"id": user_id})()


class _Context:
    def __init__(self) -> None:
        self.args: list[str] = []


class _Settings:
    operator_timezone = "America/Los_Angeles"


async def _allow(_update: object, _context: object) -> bool:
    """Auth guard that always allows the request through."""
    return False


async def _deny(_update: object, _context: object) -> bool:
    """Auth guard that always rejects the request."""
    return True


class _FakeProvider:
    """Minimal stand-in for GoogleCalendarProvider in tests."""

    def __init__(self, events: list[dict]) -> None:
        self._events = events

    def list_today_events(self, *, calendar_id: str, timezone: object) -> list[dict]:
        return self._events


@contextmanager
def _mock_session_local():
    """Context manager that yields a MagicMock without touching a real DB."""
    yield MagicMock()


_mock_user = type("User", (), {"id": 1})()


@pytest.mark.asyncio
async def test_agenda_formats_events_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Events with dateTime fields are displayed with formatted time strings."""
    sample_events = [
        {
            "summary": "Team standup",
            "start": {"dateTime": "2026-03-17T09:00:00-07:00"},
        },
        {
            "summary": "1:1 with manager",
            "start": {"dateTime": "2026-03-17T14:30:00-07:00"},
        },
    ]

    monkeypatch.setattr(agenda, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(agenda, "get_settings", lambda: _Settings())
    monkeypatch.setattr(agenda, "get_user_by_telegram_id", lambda tid, db: _mock_user)
    monkeypatch.setattr(agenda, "SessionLocal", _mock_session_local)
    monkeypatch.setattr(
        agenda,
        "GoogleCalendarProvider",
        lambda user_id, db: _FakeProvider(sample_events),
    )

    update = _Update()
    await agenda.handle(update, _Context())

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "Team standup" in reply
    assert "1:1 with manager" in reply
    # Check time formatting (9am and 2:30pm in LA timezone)
    assert "9:00 AM" in reply
    assert "2:30 PM" in reply


@pytest.mark.asyncio
async def test_agenda_empty_day_shows_no_events_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no events exist today, the handler replies with a clear empty message."""
    monkeypatch.setattr(agenda, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(agenda, "get_settings", lambda: _Settings())
    monkeypatch.setattr(agenda, "get_user_by_telegram_id", lambda tid, db: _mock_user)
    monkeypatch.setattr(agenda, "SessionLocal", _mock_session_local)
    monkeypatch.setattr(
        agenda,
        "GoogleCalendarProvider",
        lambda user_id, db: _FakeProvider([]),
    )

    update = _Update()
    await agenda.handle(update, _Context())

    assert len(update.message.replies) == 1
    assert "No events today" in update.message.replies[0]


@pytest.mark.asyncio
async def test_agenda_unauthorized_user_gets_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unauthorized users receive no reply from the agenda handler."""
    called: list[bool] = []

    monkeypatch.setattr(agenda, "reject_if_unauthorized", _deny)
    # If provider is called despite rejection, mark as failure
    monkeypatch.setattr(
        agenda,
        "GoogleCalendarProvider",
        lambda user_id, db: called.append(True) or _FakeProvider([]),
    )
    monkeypatch.setattr(agenda, "get_user_by_telegram_id", lambda tid, db: _mock_user)
    monkeypatch.setattr(agenda, "SessionLocal", _mock_session_local)

    update = _Update(user_id=999)
    await agenda.handle(update, _Context())

    assert len(update.message.replies) == 0, "Unauthorized user should receive no reply"
    assert not called, "Calendar provider should not be called for unauthorized users"


@pytest.mark.asyncio
async def test_agenda_all_day_event_shows_all_day_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All-day events (with 'date' key instead of 'dateTime') show 'All day' label."""
    sample_events = [
        {
            "summary": "Company holiday",
            "start": {"date": "2026-03-17"},
        },
    ]

    monkeypatch.setattr(agenda, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(agenda, "get_settings", lambda: _Settings())
    monkeypatch.setattr(agenda, "get_user_by_telegram_id", lambda tid, db: _mock_user)
    monkeypatch.setattr(agenda, "SessionLocal", _mock_session_local)
    monkeypatch.setattr(
        agenda,
        "GoogleCalendarProvider",
        lambda user_id, db: _FakeProvider(sample_events),
    )

    update = _Update()
    await agenda.handle(update, _Context())

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "Company holiday" in reply
    assert "All day" in reply
