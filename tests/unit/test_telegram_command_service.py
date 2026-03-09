from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass

import pytest
from helm_telegram_bot.services import command_service
from sqlalchemy.exc import SQLAlchemyError


class _Session(AbstractContextManager[object]):
    def __enter__(self) -> object:
        return object()

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class _BrokenSession(AbstractContextManager[object]):
    def __enter__(self) -> object:
        raise SQLAlchemyError("db down")

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


@dataclass
class _Action:
    id: int


@dataclass
class _Draft:
    id: int
    status: str


class _ActionRepo:
    def __init__(self, _session: object) -> None:
        self._data = [_Action(id=i) for i in range(1, 8)]

    def list_open(self) -> list[_Action]:
        return self._data


class _DraftRepo:
    def __init__(self, _session: object) -> None:
        self._by_id: dict[int, _Draft] = {
            1: _Draft(id=1, status="pending"),
            2: _Draft(id=2, status="snoozed"),
            3: _Draft(id=3, status="approved"),
        }
        self.approved_ids: list[int] = []
        self.snoozed_ids: list[int] = []

    def list_pending(self) -> list[_Draft]:
        return [_Draft(id=i, status="pending") for i in range(1, 8)]

    def get_by_id(self, draft_id: int) -> _Draft | None:
        return self._by_id.get(draft_id)

    def approve(self, draft_id: int) -> None:
        self.approved_ids.append(draft_id)

    def snooze(self, draft_id: int) -> None:
        self.snoozed_ids.append(draft_id)


@pytest.mark.parametrize("limit", [1, 3, 5])
def test_list_open_actions_applies_limit(monkeypatch: pytest.MonkeyPatch, limit: int) -> None:
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyActionItemRepository", _ActionRepo)

    service = command_service.TelegramCommandService()

    actions = service.list_open_actions(limit=limit)

    assert [a.id for a in actions] == list(range(1, limit + 1))


@pytest.mark.parametrize("limit", [1, 4, 6])
def test_list_pending_drafts_applies_limit(monkeypatch: pytest.MonkeyPatch, limit: int) -> None:
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyDraftReplyRepository", _DraftRepo)

    service = command_service.TelegramCommandService()

    drafts = service.list_pending_drafts(limit=limit)

    assert [d.id for d in drafts] == list(range(1, limit + 1))


def test_list_queries_handle_storage_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command_service, "SessionLocal", _BrokenSession)

    service = command_service.TelegramCommandService()

    assert service.list_open_actions() == []
    assert service.list_pending_drafts() == []


def test_approve_draft_happy_path_from_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _DraftRepo(object())
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyDraftReplyRepository", lambda _session: repo)

    service = command_service.TelegramCommandService()

    result = service.approve_draft(1)

    assert result.ok is True
    assert result.message == "Approved draft 1. Not sent yet."
    assert repo.approved_ids == [1]


def test_approve_draft_allows_snoozed(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _DraftRepo(object())
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyDraftReplyRepository", lambda _session: repo)

    service = command_service.TelegramCommandService()

    result = service.approve_draft(2)

    assert result.ok is True
    assert repo.approved_ids == [2]


def test_approve_draft_rejects_non_actionable_status(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _DraftRepo(object())
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyDraftReplyRepository", lambda _session: repo)

    service = command_service.TelegramCommandService()

    result = service.approve_draft(3)

    assert result.ok is False
    assert result.message == "Draft 3 is approved; cannot approve."
    assert repo.approved_ids == []


def test_approve_draft_handles_missing_id(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _DraftRepo(object())
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyDraftReplyRepository", lambda _session: repo)

    service = command_service.TelegramCommandService()

    result = service.approve_draft(999)

    assert result.ok is False
    assert result.message == "Draft 999 not found."


def test_approve_draft_handles_storage_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command_service, "SessionLocal", _BrokenSession)

    service = command_service.TelegramCommandService()

    result = service.approve_draft(1)

    assert result.ok is False
    assert result.message == "Storage unavailable."


def test_snooze_draft_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _DraftRepo(object())
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyDraftReplyRepository", lambda _session: repo)

    service = command_service.TelegramCommandService()

    result = service.snooze_draft(1)

    assert result.ok is True
    assert result.message == "Snoozed draft 1 for later review."
    assert repo.snoozed_ids == [1]


def test_snooze_draft_rejects_non_pending_status(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _DraftRepo(object())
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyDraftReplyRepository", lambda _session: repo)

    service = command_service.TelegramCommandService()

    result = service.snooze_draft(2)

    assert result.ok is False
    assert result.message == "Draft 2 is snoozed; cannot snooze."
    assert repo.snoozed_ids == []


def test_snooze_draft_handles_missing_id(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _DraftRepo(object())
    monkeypatch.setattr(command_service, "SessionLocal", _Session)
    monkeypatch.setattr(command_service, "SQLAlchemyDraftReplyRepository", lambda _session: repo)

    service = command_service.TelegramCommandService()

    result = service.snooze_draft(999)

    assert result.ok is False
    assert result.message == "Draft 999 not found."


def test_snooze_draft_handles_storage_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command_service, "SessionLocal", _BrokenSession)

    service = command_service.TelegramCommandService()

    result = service.snooze_draft(1)

    assert result.ok is False
    assert result.message == "Storage unavailable."
