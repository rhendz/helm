from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import EmailThreadORM
from helm_storage.repositories.contracts import NewEmailThread


class SQLAlchemyEmailThreadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, thread_id: int) -> EmailThreadORM | None:
        stmt = select(EmailThreadORM).where(EmailThreadORM.id == thread_id)
        return self._session.execute(stmt).scalars().first()

    def get_by_provider_thread_id(self, provider_thread_id: str) -> EmailThreadORM | None:
        stmt = select(EmailThreadORM).where(EmailThreadORM.provider_thread_id == provider_thread_id)
        return self._session.execute(stmt).scalars().first()

    def create(self, item: NewEmailThread) -> EmailThreadORM:
        record = EmailThreadORM(
            provider_thread_id=item.provider_thread_id,
            business_state=item.business_state,
            visible_labels=_serialize_labels(item.visible_labels),
            current_summary=item.current_summary,
            latest_confidence_band=item.latest_confidence_band,
            resurfacing_source=item.resurfacing_source,
            action_reason=item.action_reason,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_or_create(self, item: NewEmailThread) -> EmailThreadORM:
        existing = self.get_by_provider_thread_id(item.provider_thread_id)
        if existing is not None:
            return existing
        return self.create(item)

    def update_state(
        self,
        thread_id: int,
        *,
        business_state: str,
        visible_labels: tuple[str, ...],
        latest_confidence_band: str | None,
        resurfacing_source: str | None,
        action_reason: str | None,
        current_summary: str | None,
        last_message_id: int | None = None,
        last_inbound_message_id: int | None = None,
        last_outbound_message_id: int | None = None,
    ) -> EmailThreadORM | None:
        record = self.get_by_id(thread_id)
        if record is None:
            return None
        record.business_state = business_state
        record.visible_labels = _serialize_labels(visible_labels)
        record.latest_confidence_band = latest_confidence_band
        record.resurfacing_source = resurfacing_source
        record.action_reason = action_reason
        record.current_summary = current_summary
        if last_message_id is not None:
            record.last_message_id = last_message_id
        if last_inbound_message_id is not None:
            record.last_inbound_message_id = last_inbound_message_id
        if last_outbound_message_id is not None:
            record.last_outbound_message_id = last_outbound_message_id
        record.summary_updated_at = datetime.now(tz=UTC)
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record


def _serialize_labels(labels: tuple[str, ...]) -> str:
    return ",".join(sorted(set(labels)))
