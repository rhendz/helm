from helm_connectors.linkedin import NormalizedLinkedInMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import LinkedInMessageORM, LinkedInThreadORM


class SQLAlchemyLinkedInMessageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_provider_message_id(self, provider_message_id: str) -> LinkedInMessageORM | None:
        statement = select(LinkedInMessageORM).where(
            LinkedInMessageORM.provider_message_id == provider_message_id
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_thread_by_external_id(self, external_thread_id: str) -> LinkedInThreadORM | None:
        statement = select(LinkedInThreadORM).where(
            LinkedInThreadORM.external_thread_id == external_thread_id
        )
        return self._session.execute(statement).scalar_one_or_none()

    def upsert_thread(self, *, external_thread_id: str, summary: str | None) -> LinkedInThreadORM:
        thread = self.get_thread_by_external_id(external_thread_id)
        if thread is None:
            thread = LinkedInThreadORM(
                external_thread_id=external_thread_id,
                thread_summary=summary,
            )
            self._session.add(thread)
            self._session.flush()
            return thread

        if summary:
            thread.thread_summary = summary
            self._session.flush()
        return thread

    def upsert_from_normalized(self, message: NormalizedLinkedInMessage) -> LinkedInMessageORM:
        self.upsert_thread(
            external_thread_id=message.provider_thread_id,
            summary=message.body_text[:280] if message.body_text else None,
        )
        record = self.get_by_provider_message_id(message.provider_message_id)
        if record is None:
            record = LinkedInMessageORM(
                provider_message_id=message.provider_message_id,
                thread_id=message.provider_thread_id,
                sender_name=message.sender_name,
                body_text=message.body_text,
                received_at=message.received_at,
            )
            self._session.add(record)
        else:
            record.thread_id = message.provider_thread_id
            record.sender_name = message.sender_name
            record.body_text = message.body_text
            record.received_at = message.received_at

        self._session.commit()
        self._session.refresh(record)
        return record
