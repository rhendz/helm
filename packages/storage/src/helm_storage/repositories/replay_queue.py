from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import ReplayQueueORM

_ACTIVE_REPLAY_STATUSES = ("pending", "processing")


class SQLAlchemyReplayQueueRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_for_agent_run(self, *, agent_run_id: int) -> ReplayQueueORM | None:
        statement = (
            select(ReplayQueueORM)
            .where(
                ReplayQueueORM.agent_run_id == agent_run_id,
                ReplayQueueORM.status.in_(_ACTIVE_REPLAY_STATUSES),
            )
            .order_by(ReplayQueueORM.id.desc())
        )
        return self._session.execute(statement).scalar_one_or_none()

    def enqueue_from_failed_run(
        self, *, agent_run_id: int, source_type: str, source_id: str | None
    ) -> tuple[ReplayQueueORM, bool]:
        active = self.get_active_for_agent_run(agent_run_id=agent_run_id)
        if active is not None:
            return active, False

        item = ReplayQueueORM(
            agent_run_id=agent_run_id,
            source_type=source_type,
            source_id=source_id,
            status="pending",
            attempts=0,
        )
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return item, True

    def list_pending(self, *, limit: int) -> list[ReplayQueueORM]:
        statement = (
            select(ReplayQueueORM)
            .where(ReplayQueueORM.status == "pending")
            .order_by(ReplayQueueORM.id.asc())
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())

    def mark_processing(self, item_id: int) -> ReplayQueueORM | None:
        item = self.get_by_id(item_id)
        if item is None:
            return None
        if item.status != "pending":
            return item
        item.status = "processing"
        item.attempts += 1
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def mark_completed(self, item_id: int) -> None:
        item = self.get_by_id(item_id)
        if item is None:
            return
        item.status = "completed"
        item.last_error = None
        self._session.add(item)
        self._session.commit()

    def mark_failed(self, item_id: int, *, error_message: str) -> None:
        item = self.get_by_id(item_id)
        if item is None:
            return
        item.status = "failed"
        item.last_error = error_message[:4000]
        self._session.add(item)
        self._session.commit()

    def get_by_id(self, item_id: int) -> ReplayQueueORM | None:
        statement = select(ReplayQueueORM).where(ReplayQueueORM.id == item_id)
        return self._session.execute(statement).scalar_one_or_none()
