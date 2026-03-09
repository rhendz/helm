from datetime import datetime

from helm_connectors.gmail import NormalizedGmailMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import EmailMessageORM


class SQLAlchemyEmailMessageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_provider_message_id(self, provider_message_id: str) -> EmailMessageORM | None:
        stmt = select(EmailMessageORM).where(
            EmailMessageORM.provider_message_id == provider_message_id
        )
        return self._session.execute(stmt).scalars().first()

    def upsert_from_normalized(self, message: NormalizedGmailMessage) -> EmailMessageORM:
        record = self.get_by_provider_message_id(message.provider_message_id)
        if record is None:
            record = EmailMessageORM(
                provider_message_id=message.provider_message_id,
                thread_id=message.provider_thread_id,
                from_address=message.from_address,
                subject=message.subject,
                body_text=message.body_text,
                received_at=message.received_at,
            )
        else:
            record.thread_id = message.provider_thread_id
            record.from_address = message.from_address
            record.subject = message.subject
            record.body_text = message.body_text
            record.received_at = message.received_at
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def mark_processed(self, provider_message_id: str, *, processed_at: datetime) -> None:
        record = self.get_by_provider_message_id(provider_message_id)
        if record is None:
            return
        record.processed_at = processed_at
        self._session.add(record)
        self._session.commit()
