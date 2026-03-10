from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import DraftTransitionAuditORM


class SQLAlchemyDraftTransitionAuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        draft_id: int,
        action: str,
        from_status: str | None,
        to_status: str | None,
        success: bool,
        reason: str | None,
    ) -> DraftTransitionAuditORM:
        record = DraftTransitionAuditORM(
            draft_id=draft_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            success=success,
            reason=reason,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def list_recent_failed(self, *, limit: int = 20) -> list[DraftTransitionAuditORM]:
        stmt = (
            select(DraftTransitionAuditORM)
            .where(DraftTransitionAuditORM.success.is_(False))
            .order_by(DraftTransitionAuditORM.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_for_draft(self, *, draft_id: int) -> list[DraftTransitionAuditORM]:
        stmt = (
            select(DraftTransitionAuditORM)
            .where(DraftTransitionAuditORM.draft_id == draft_id)
            .order_by(DraftTransitionAuditORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())
