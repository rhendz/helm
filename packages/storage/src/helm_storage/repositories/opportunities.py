from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import OpportunityORM


class SQLAlchemyOpportunityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_open(self, *, limit: int) -> list[OpportunityORM]:
        statement = (
            select(OpportunityORM)
            .where(OpportunityORM.status == "open")
            .order_by(OpportunityORM.priority_score.desc(), OpportunityORM.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())
