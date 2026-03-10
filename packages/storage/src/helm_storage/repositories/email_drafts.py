from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import EmailDraftORM
from helm_storage.repositories.contracts import NewEmailDraft


class SQLAlchemyEmailDraftRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent(self, *, limit: int | None = None) -> list[EmailDraftORM]:
        stmt = select(EmailDraftORM).order_by(
            EmailDraftORM.updated_at.desc(),
            EmailDraftORM.id.desc(),
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def create(self, item: NewEmailDraft) -> EmailDraftORM:
        record = EmailDraftORM(
            email_thread_id=item.email_thread_id,
            action_proposal_id=item.action_proposal_id,
            draft_body=item.draft_body,
            draft_subject=item.draft_subject,
            status=item.status,
            approval_status=item.approval_status,
            model_name=item.model_name,
            prompt_version=item.prompt_version,
            draft_reasoning_artifact_ref=item.draft_reasoning_artifact_ref,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_by_id(self, draft_id: int) -> EmailDraftORM | None:
        stmt = select(EmailDraftORM).where(EmailDraftORM.id == draft_id)
        return self._session.execute(stmt).scalars().first()

    def get_latest_for_thread(self, *, email_thread_id: int) -> EmailDraftORM | None:
        stmt = (
            select(EmailDraftORM)
            .where(EmailDraftORM.email_thread_id == email_thread_id)
            .order_by(EmailDraftORM.id.desc())
        )
        return self._session.execute(stmt).scalars().first()

    def set_approval_status(self, draft_id: int, *, approval_status: str) -> bool:
        record = self.get_by_id(draft_id)
        if record is None:
            return False
        record.approval_status = approval_status
        self._session.add(record)
        self._session.commit()
        return True
