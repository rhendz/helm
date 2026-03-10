from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import ScheduledThreadTaskORM
from helm_storage.repositories.contracts import NewScheduledThreadTask


class SQLAlchemyScheduledThreadTaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, item: NewScheduledThreadTask) -> ScheduledThreadTaskORM:
        record = ScheduledThreadTaskORM(
            email_thread_id=item.email_thread_id,
            task_type=item.task_type,
            created_by=item.created_by,
            due_at=item.due_at,
            status=item.status,
            reason=item.reason,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def list_for_thread(self, *, email_thread_id: int) -> list[ScheduledThreadTaskORM]:
        stmt = (
            select(ScheduledThreadTaskORM)
            .where(ScheduledThreadTaskORM.email_thread_id == email_thread_id)
            .order_by(ScheduledThreadTaskORM.due_at.asc(), ScheduledThreadTaskORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_due(
        self,
        *,
        due_before: datetime,
        status: str = "pending",
        limit: int | None = None,
    ) -> list[ScheduledThreadTaskORM]:
        stmt = (
            select(ScheduledThreadTaskORM)
            .where(ScheduledThreadTaskORM.status == status)
            .where(ScheduledThreadTaskORM.due_at <= due_before)
            .order_by(ScheduledThreadTaskORM.due_at.asc(), ScheduledThreadTaskORM.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def mark_completed(self, task_id: int) -> bool:
        record = self._session.get(ScheduledThreadTaskORM, task_id)
        if record is None:
            return False
        record.status = "completed"
        self._session.add(record)
        self._session.commit()
        return True
