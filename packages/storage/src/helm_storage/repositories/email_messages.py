from datetime import datetime

from helm_connectors.gmail import NormalizedGmailMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import EmailMessageORM
from helm_storage.repositories.contracts import NewOutboundEmailMessage


class SQLAlchemyEmailMessageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_provider_message_id(self, provider_message_id: str) -> EmailMessageORM | None:
        stmt = select(EmailMessageORM).where(
            EmailMessageORM.provider_message_id == provider_message_id
        )
        return self._session.execute(stmt).scalars().first()

    def list_for_thread(self, *, email_thread_id: int) -> list[EmailMessageORM]:
        stmt = (
            select(EmailMessageORM)
            .where(EmailMessageORM.email_thread_id == email_thread_id)
            .order_by(EmailMessageORM.received_at.asc(), EmailMessageORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_latest_inbound_for_thread(self, *, email_thread_id: int) -> EmailMessageORM | None:
        stmt = (
            select(EmailMessageORM)
            .where(
                EmailMessageORM.email_thread_id == email_thread_id,
                EmailMessageORM.direction == "inbound",
            )
            .order_by(EmailMessageORM.received_at.desc(), EmailMessageORM.id.desc())
        )
        return self._session.execute(stmt).scalars().first()

    def upsert_from_normalized(
        self,
        message: NormalizedGmailMessage,
        *,
        email_thread_id: int | None = None,
        direction: str = "inbound",
        source_draft_id: int | None = None,
    ) -> EmailMessageORM:
        record = self.get_by_provider_message_id(message.provider_message_id)
        if record is None:
            record = EmailMessageORM(
                provider_message_id=message.provider_message_id,
                provider_thread_id=message.provider_thread_id,
                email_thread_id=email_thread_id,
                source_draft_id=source_draft_id,
                direction=direction,
                from_address=message.from_address,
                subject=message.subject,
                snippet=message.body_text[:200] or None,
                body_text=message.body_text,
                received_at=message.received_at,
                normalized_at=message.normalized_at,
                source=message.source,
            )
        else:
            record.provider_thread_id = message.provider_thread_id
            record.email_thread_id = email_thread_id
            record.source_draft_id = source_draft_id
            record.direction = direction
            record.from_address = message.from_address
            record.subject = message.subject
            record.snippet = message.body_text[:200] or None
            record.body_text = message.body_text
            record.received_at = message.received_at
            record.normalized_at = message.normalized_at
            record.source = message.source
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def create_outbound(self, item: NewOutboundEmailMessage) -> EmailMessageORM:
        record = EmailMessageORM(
            provider_message_id=item.provider_message_id,
            provider_thread_id=item.provider_thread_id,
            email_thread_id=item.email_thread_id,
            source_draft_id=item.source_draft_id,
            direction="outbound",
            from_address=item.from_address,
            to_addresses=",".join(item.to_addresses),
            subject=item.subject,
            snippet=item.body_text[:200] or None,
            body_text=item.body_text,
            received_at=item.received_at,
            normalized_at=item.normalized_at,
            source=item.source,
        )
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
