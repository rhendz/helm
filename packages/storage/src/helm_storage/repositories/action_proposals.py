from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import ActionProposalORM
from helm_storage.repositories.contracts import NewActionProposal


class SQLAlchemyActionProposalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent(self, *, limit: int | None = None) -> list[ActionProposalORM]:
        stmt = select(ActionProposalORM).order_by(
            ActionProposalORM.updated_at.desc(),
            ActionProposalORM.id.desc(),
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def create(self, item: NewActionProposal) -> ActionProposalORM:
        record = ActionProposalORM(
            email_thread_id=item.email_thread_id,
            proposal_type=item.proposal_type,
            rationale=item.rationale,
            confidence_band=item.confidence_band,
            status=item.status,
            model_name=item.model_name,
            prompt_version=item.prompt_version,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_latest_for_thread(self, *, email_thread_id: int) -> ActionProposalORM | None:
        stmt = (
            select(ActionProposalORM)
            .where(ActionProposalORM.email_thread_id == email_thread_id)
            .order_by(ActionProposalORM.id.desc())
        )
        return self._session.execute(stmt).scalars().first()

    def list_for_thread(self, *, email_thread_id: int) -> list[ActionProposalORM]:
        stmt = (
            select(ActionProposalORM)
            .where(ActionProposalORM.email_thread_id == email_thread_id)
            .order_by(ActionProposalORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())
