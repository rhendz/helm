from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import EmailDraftORM
from helm_storage.repositories.contracts import EmailDraftContentPatch, NewEmailDraft


class SQLAlchemyEmailDraftRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent(
        self,
        *,
        status: str | None = None,
        approval_status: str | None = None,
        limit: int | None = None,
    ) -> list[EmailDraftORM]:
        stmt = select(EmailDraftORM)
        if status is not None:
            stmt = stmt.where(EmailDraftORM.status == status)
        if approval_status is not None:
            stmt = stmt.where(EmailDraftORM.approval_status == approval_status)
        stmt = stmt.order_by(
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

    def list_for_thread(self, *, email_thread_id: int) -> list[EmailDraftORM]:
        stmt = (
            select(EmailDraftORM)
            .where(EmailDraftORM.email_thread_id == email_thread_id)
            .order_by(EmailDraftORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def set_approval_status(self, draft_id: int, *, approval_status: str) -> bool:
        record = self.get_by_id(draft_id)
        if record is None:
            return False
        record.approval_status = approval_status
        self._session.add(record)
        self._session.commit()
        return True

    def update_content(self, draft_id: int, patch: EmailDraftContentPatch) -> EmailDraftORM | None:
        record = self.get_by_id(draft_id)
        if record is None:
            return None
        record.draft_body = patch.draft_body
        record.draft_subject = patch.draft_subject
        record.action_proposal_id = patch.action_proposal_id
        if patch.status is not None:
            record.status = patch.status
        if patch.approval_status is not None:
            record.approval_status = patch.approval_status
        record.model_name = patch.model_name
        record.prompt_version = patch.prompt_version
        record.draft_reasoning_artifact_ref = patch.draft_reasoning_artifact_ref
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def set_reasoning_artifact_ref(self, draft_id: int, *, artifact_ref: str) -> bool:
        record = self.get_by_id(draft_id)
        if record is None:
            return False
        record.draft_reasoning_artifact_ref = artifact_ref
        self._session.add(record)
        self._session.commit()
        return True
