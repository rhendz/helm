from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import DraftReplyORM


@dataclass(slots=True)
class DraftReplyCreate:
    channel_type: str
    thread_id: str
    draft_text: str
    contact_id: int | None = None
    tone: str | None = None
    status: str = "pending"


class DraftReplyRepository(Protocol):
    def create(self, payload: DraftReplyCreate) -> DraftReplyORM: ...

    def list_pending(self) -> list[DraftReplyORM]: ...

    def get_by_id(self, draft_id: int) -> DraftReplyORM | None: ...

    def approve(self, draft_id: int) -> DraftReplyORM | None: ...

    def snooze(self, draft_id: int, *, hours: int = 24) -> DraftReplyORM | None: ...


class SQLAlchemyDraftReplyRepository(DraftReplyRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, payload: DraftReplyCreate) -> DraftReplyORM:
        draft = DraftReplyORM(
            channel_type=payload.channel_type,
            thread_id=payload.thread_id,
            contact_id=payload.contact_id,
            draft_text=payload.draft_text,
            tone=payload.tone,
            status=payload.status,
        )
        self._session.add(draft)
        self._session.commit()
        self._session.refresh(draft)
        return draft

    def list_pending(self) -> list[DraftReplyORM]:
        stmt = (
            select(DraftReplyORM)
            .where(DraftReplyORM.status.in_(("pending", "snoozed")))
            .order_by(DraftReplyORM.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())

    def get_by_id(self, draft_id: int) -> DraftReplyORM | None:
        return self._session.get(DraftReplyORM, draft_id)

    def approve(self, draft_id: int) -> DraftReplyORM | None:
        draft = self.get_by_id(draft_id)
        if draft is None:
            return None
        draft.status = "approved"
        self._session.commit()
        self._session.refresh(draft)
        return draft

    def snooze(self, draft_id: int, *, hours: int = 24) -> DraftReplyORM | None:
        draft = self.get_by_id(draft_id)
        if draft is None:
            return None
        draft.status = "snoozed"
        if hasattr(draft, "updated_at"):
            draft.updated_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(draft)
        return draft
