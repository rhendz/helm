from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import EmailDeepSeedQueueORM
from helm_storage.repositories.contracts import (
    EmailDeepSeedQueuePatch,
    NewEmailDeepSeedQueueItem,
)

_ACTIVE_DEEP_SEED_STATUSES = ("pending", "processing")


class SQLAlchemyEmailDeepSeedQueueRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, item: NewEmailDeepSeedQueueItem) -> tuple[EmailDeepSeedQueueORM, bool]:
        active = self.get_active_for_provider_thread(
            source_type=item.source_type,
            provider_thread_id=item.provider_thread_id,
        )
        if active is not None:
            return active, False

        record = EmailDeepSeedQueueORM(
            source_type=item.source_type,
            provider_thread_id=item.provider_thread_id,
            status=item.status,
            seed_reason=item.seed_reason,
            message_count=item.message_count,
            latest_received_at=item.latest_received_at,
            sample_subject=item.sample_subject,
            from_addresses=list(item.from_addresses),
            thread_payload=item.thread_payload,
            attempts=item.attempts,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record, True

    def get_by_id(self, item_id: int) -> EmailDeepSeedQueueORM | None:
        statement = select(EmailDeepSeedQueueORM).where(EmailDeepSeedQueueORM.id == item_id)
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_for_provider_thread(
        self,
        *,
        source_type: str,
        provider_thread_id: str,
    ) -> EmailDeepSeedQueueORM | None:
        statement = (
            select(EmailDeepSeedQueueORM)
            .where(
                EmailDeepSeedQueueORM.source_type == source_type,
                EmailDeepSeedQueueORM.provider_thread_id == provider_thread_id,
                EmailDeepSeedQueueORM.status.in_(_ACTIVE_DEEP_SEED_STATUSES),
            )
            .order_by(EmailDeepSeedQueueORM.id.desc())
        )
        return self._session.execute(statement).scalar_one_or_none()

    def list_recent(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[EmailDeepSeedQueueORM]:
        statement = select(EmailDeepSeedQueueORM).order_by(
            EmailDeepSeedQueueORM.created_at.desc(),
            EmailDeepSeedQueueORM.id.desc(),
        )
        if status is not None:
            statement = statement.where(EmailDeepSeedQueueORM.status == status)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self._session.execute(statement).scalars().all())

    def mark_processing(self, item_id: int) -> EmailDeepSeedQueueORM | None:
        item = self.get_by_id(item_id)
        if item is None:
            return None
        if item.status != "pending":
            return item
        item.status = "processing"
        item.attempts += 1
        item.last_error = None
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def mark_completed(
        self,
        item_id: int,
        *,
        email_thread_id: int | None,
        completed_at: datetime,
    ) -> EmailDeepSeedQueueORM | None:
        return self._update(
            item_id,
            EmailDeepSeedQueuePatch(
                status="completed",
                last_error=None,
                email_thread_id=email_thread_id,
                completed_at=completed_at,
            ),
        )

    def mark_failed(self, item_id: int, *, error_message: str) -> EmailDeepSeedQueueORM | None:
        return self._update(
            item_id,
            EmailDeepSeedQueuePatch(
                status="failed",
                last_error=error_message[:4000],
                completed_at=datetime.now(tz=UTC),
            ),
        )

    def _update(self, item_id: int, patch: EmailDeepSeedQueuePatch) -> EmailDeepSeedQueueORM | None:
        item = self.get_by_id(item_id)
        if item is None:
            return None
        item.status = patch.status
        if patch.attempts is not None:
            item.attempts = patch.attempts
        item.last_error = patch.last_error
        item.email_thread_id = patch.email_thread_id
        item.completed_at = patch.completed_at
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return item
