from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import DigestItemORM
from helm_storage.repositories.contracts import NewDigestItem


class SQLAlchemyDigestItemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_top(self, *, limit: int = 10, domain: str | None = None) -> list[DigestItemORM]:
        stmt = select(DigestItemORM)
        if domain:
            stmt = stmt.where(DigestItemORM.domain == domain)
        stmt = stmt.order_by(DigestItemORM.priority.asc(), DigestItemORM.id.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def create(self, item: NewDigestItem) -> DigestItemORM:
        record = DigestItemORM(
            domain=item.domain,
            title=item.title,
            summary=item.summary,
            priority=item.priority,
            related_contact_id=item.related_contact_id,
            related_action_id=item.related_action_id,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record
