from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import DigestItemORM


@dataclass(slots=True)
class DigestItemCreate:
    domain: str
    title: str
    summary: str
    priority: int = 3
    related_contact_id: int | None = None
    related_action_id: int | None = None


class DigestItemRepository(Protocol):
    def create(self, payload: DigestItemCreate) -> DigestItemORM: ...

    def list_recent(self, limit: int = 10) -> list[DigestItemORM]: ...


class SQLAlchemyDigestItemRepository(DigestItemRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, payload: DigestItemCreate) -> DigestItemORM:
        item = DigestItemORM(
            domain=payload.domain,
            title=payload.title,
            summary=payload.summary,
            priority=payload.priority,
            related_contact_id=payload.related_contact_id,
            related_action_id=payload.related_action_id,
        )
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def list_recent(self, limit: int = 10) -> list[DigestItemORM]:
        stmt = select(DigestItemORM).order_by(DigestItemORM.created_at.desc()).limit(limit)
        return list(self._session.scalars(stmt).all())
