from datetime import UTC, datetime, timedelta

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

    def list_stale(
        self,
        *,
        stale_after_hours: int = 72,
        include_snoozed: bool = True,
        limit: int | None = None,
        now: datetime | None = None,
    ) -> list[DraftReplyORM]:
        cutoff = (now or datetime.now(tz=UTC)) - timedelta(hours=stale_after_hours)
        statuses = ["pending", "snoozed"] if include_snoozed else ["pending"]
        stmt = (
            select(DraftReplyORM)
            .where(DraftReplyORM.status.in_(statuses))
            .where(DraftReplyORM.updated_at <= cutoff)
            .order_by(DraftReplyORM.updated_at.asc(), DraftReplyORM.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def get_by_id(self, draft_id: int) -> DraftReplyORM | None:
        stmt = select(DraftReplyORM).where(DraftReplyORM.id == draft_id)
        return self._session.execute(stmt).scalars().first()

    def get_latest_for_thread(self, *, thread_id: str) -> DraftReplyORM | None:
        stmt = (
            select(DraftReplyORM)
            .where(DraftReplyORM.thread_id == thread_id)
            .order_by(DraftReplyORM.id.desc())
        )
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

    def requeue(self, draft_id: int) -> bool:
        draft = self.get_by_id(draft_id)
        if draft is None:
            return False
        draft.status = "pending"
        self._session.add(draft)
        self._session.commit()
        return True
