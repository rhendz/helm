from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import DraftReplyORM


class SQLAlchemyDraftReplyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_pending(self) -> list[DraftReplyORM]:
        stmt = (
            select(DraftReplyORM)
            .where(DraftReplyORM.status.in_(["pending", "snoozed"]))
            .order_by(DraftReplyORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_by_id(self, draft_id: int) -> DraftReplyORM | None:
        stmt = select(DraftReplyORM).where(DraftReplyORM.id == draft_id)
        return self._session.execute(stmt).scalars().first()

    def approve(self, draft_id: int) -> None:
        draft = self.get_by_id(draft_id)
        if draft is None:
            return
        draft.status = "approved"
        self._session.add(draft)
        self._session.commit()

    def snooze(self, draft_id: int) -> None:
        draft = self.get_by_id(draft_id)
        if draft is None:
            return
        draft.status = "snoozed"
        self._session.add(draft)
        self._session.commit()
