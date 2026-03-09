from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import ActionItemORM


@dataclass(slots=True)
class ActionItemCreate:
    title: str
    description: str | None = None
    priority: int = 3
    status: str = "open"
    source_type: str | None = None
    source_id: str | None = None
    due_at: datetime | None = None


class ActionItemRepository(Protocol):
    def create(self, payload: ActionItemCreate) -> ActionItemORM: ...

    def list_open(self) -> list[ActionItemORM]: ...


class SQLAlchemyActionItemRepository(ActionItemRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, payload: ActionItemCreate) -> ActionItemORM:
        item = ActionItemORM(
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            status=payload.status,
            source_type=payload.source_type,
            source_id=payload.source_id,
            due_at=payload.due_at,
        )
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def list_open(self) -> list[ActionItemORM]:
        stmt = (
            select(ActionItemORM)
            .where(ActionItemORM.status == "open")
            .order_by(ActionItemORM.priority.asc(), ActionItemORM.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())
