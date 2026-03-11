from sqlalchemy import func, select
from sqlalchemy.orm import Session

from helm_storage.models import EmailSendAttemptORM
from helm_storage.repositories.contracts import EmailSendAttemptPatch, NewEmailSendAttempt


class SQLAlchemyEmailSendAttemptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, item: NewEmailSendAttempt) -> EmailSendAttemptORM:
        record = EmailSendAttemptORM(
            draft_id=item.draft_id,
            email_thread_id=item.email_thread_id,
            attempt_number=item.attempt_number,
            status=item.status,
            failure_class=item.failure_class,
            failure_message=item.failure_message,
            provider_error_code=item.provider_error_code,
            provider_message_id=item.provider_message_id,
            started_at=item.started_at,
            completed_at=item.completed_at,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_by_id(self, attempt_id: int) -> EmailSendAttemptORM | None:
        stmt = select(EmailSendAttemptORM).where(EmailSendAttemptORM.id == attempt_id)
        return self._session.execute(stmt).scalars().first()

    def list_for_draft(self, *, draft_id: int) -> list[EmailSendAttemptORM]:
        stmt = (
            select(EmailSendAttemptORM)
            .where(EmailSendAttemptORM.draft_id == draft_id)
            .order_by(EmailSendAttemptORM.attempt_number.desc(), EmailSendAttemptORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def count_for_draft(self, *, draft_id: int) -> int:
        stmt = select(func.count()).select_from(EmailSendAttemptORM).where(
            EmailSendAttemptORM.draft_id == draft_id
        )
        return int(self._session.execute(stmt).scalar_one())

    def get_success_for_draft(self, *, draft_id: int) -> EmailSendAttemptORM | None:
        stmt = (
            select(EmailSendAttemptORM)
            .where(
                EmailSendAttemptORM.draft_id == draft_id,
                EmailSendAttemptORM.status == "succeeded",
            )
            .order_by(EmailSendAttemptORM.attempt_number.desc(), EmailSendAttemptORM.id.desc())
        )
        return self._session.execute(stmt).scalars().first()

    def update(self, attempt_id: int, patch: EmailSendAttemptPatch) -> EmailSendAttemptORM | None:
        record = self.get_by_id(attempt_id)
        if record is None:
            return None
        record.status = patch.status
        record.completed_at = patch.completed_at
        record.failure_class = patch.failure_class
        record.failure_message = patch.failure_message
        record.provider_error_code = patch.provider_error_code
        record.provider_message_id = patch.provider_message_id
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record
