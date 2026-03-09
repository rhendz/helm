from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import ActionItemORM
from helm_storage.repositories.contracts import NewActionItem


class SQLAlchemyActionItemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_open(self, *, limit: int | None = None) -> list[ActionItemORM]:
        stmt = (
            select(ActionItemORM)
            .where(ActionItemORM.status == "open")
            .order_by(ActionItemORM.priority.asc(), ActionItemORM.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def get_by_id(self, action_id: int) -> ActionItemORM | None:
        stmt = select(ActionItemORM).where(ActionItemORM.id == action_id)
        return self._session.execute(stmt).scalars().first()

    def create(self, item: NewActionItem) -> ActionItemORM:
        record = ActionItemORM(
            source_type=item.source_type,
            source_id=item.source_id,
            title=item.title,
            description=item.description,
            priority=item.priority,
            status=item.status,
            due_at=item.due_at,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record
