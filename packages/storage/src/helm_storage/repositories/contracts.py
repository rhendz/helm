from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from helm_storage.models import ActionItemORM, DigestItemORM, DraftReplyORM


@dataclass(frozen=True, slots=True)
class NewActionItem:
    source_type: str
    source_id: str | None
    title: str
    description: str | None = None
    priority: int = 3
    status: str = "open"
    due_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewDraftReply:
    channel_type: str = "email"
    thread_id: str | None = None
    contact_id: int | None = None
    draft_text: str = ""
    tone: str | None = None
    status: str = "pending"


@dataclass(frozen=True, slots=True)
class NewDigestItem:
    domain: str
    title: str
    summary: str
    priority: int = 3
    related_contact_id: int | None = None
    related_action_id: int | None = None


@runtime_checkable
class ActionItemRepository(Protocol):
    def list_open(self, *, limit: int | None = None) -> list[ActionItemORM]: ...

    def get_by_id(self, action_id: int) -> ActionItemORM | None: ...

    def create(self, item: NewActionItem) -> ActionItemORM: ...


@runtime_checkable
class DraftReplyRepository(Protocol):
    def list_pending(self, *, limit: int | None = None) -> list[DraftReplyORM]: ...

    def get_by_id(self, draft_id: int) -> DraftReplyORM | None: ...

    def create(self, item: NewDraftReply) -> DraftReplyORM: ...

    def approve(self, draft_id: int) -> bool: ...

    def snooze(self, draft_id: int) -> bool: ...


@runtime_checkable
class DigestItemRepository(Protocol):
    def list_top(self, *, limit: int = 10, domain: str | None = None) -> list[DigestItemORM]: ...

    def create(self, item: NewDigestItem) -> DigestItemORM: ...
