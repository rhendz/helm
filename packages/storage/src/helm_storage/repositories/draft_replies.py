from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import DraftReplyORM
from helm_storage.repositories.contracts import NewDraftReply


class SQLAlchemyDraftReplyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_pending(self, *, limit: int | None = None) -> list[DraftReplyORM]:
        stmt = (
            select(DraftReplyORM)
            .where(DraftReplyORM.status.in_(["pending", "snoozed"]))
            .order_by(DraftReplyORM.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def get_by_id(self, draft_id: int) -> DraftReplyORM | None:
        stmt = select(DraftReplyORM).where(DraftReplyORM.id == draft_id)
        return self._session.execute(stmt).scalars().first()

    def create(self, item: NewDraftReply) -> DraftReplyORM:
        record = DraftReplyORM(
            channel_type=item.channel_type,
            thread_id=item.thread_id,
            contact_id=item.contact_id,
            draft_text=item.draft_text,
            tone=item.tone,
            status=item.status,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def approve(self, draft_id: int) -> bool:
        draft = self.get_by_id(draft_id)
        if draft is None:
            return False
        draft.status = "approved"
        self._session.add(draft)
        self._session.commit()
        return True

    def snooze(self, draft_id: int) -> bool:
        draft = self.get_by_id(draft_id)
        if draft is None:
            return False
        draft.status = "snoozed"
        self._session.add(draft)
        self._session.commit()
        return True
