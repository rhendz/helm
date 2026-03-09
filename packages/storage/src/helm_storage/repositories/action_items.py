from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import ActionItemORM


class SQLAlchemyActionItemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_open(self) -> list[ActionItemORM]:
        stmt = (
            select(ActionItemORM)
            .where(ActionItemORM.status == "open")
            .order_by(ActionItemORM.priority.asc(), ActionItemORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())
