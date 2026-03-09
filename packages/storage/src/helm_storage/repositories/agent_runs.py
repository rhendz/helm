from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import AgentRunORM


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_TERMINAL_STATUSES = {AgentRunStatus.SUCCEEDED.value, AgentRunStatus.FAILED.value}


class SQLAlchemyAgentRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start_run(
        self,
        *,
        agent_name: str,
        source_type: str,
        source_id: str | None = None,
    ) -> AgentRunORM:
        run = AgentRunORM(
            agent_name=agent_name,
            source_type=source_type,
            source_id=source_id,
            status=AgentRunStatus.RUNNING.value,
            started_at=datetime.utcnow(),
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def mark_succeeded(self, run_id: int) -> None:
        run = self.get_by_id(run_id)
        if run is None:
            return
        if run.status in _TERMINAL_STATUSES:
            return
        if run.status != AgentRunStatus.RUNNING.value:
            return
        run.status = AgentRunStatus.SUCCEEDED.value
        run.completed_at = run.completed_at or datetime.utcnow()
        run.error_message = None
        self._session.add(run)
        self._session.commit()

    def mark_failed(self, run_id: int, error_message: str) -> None:
        run = self.get_by_id(run_id)
        if run is None:
            return
        if run.status in _TERMINAL_STATUSES:
            return
        if run.status != AgentRunStatus.RUNNING.value:
            return
        run.status = AgentRunStatus.FAILED.value
        run.completed_at = run.completed_at or datetime.utcnow()
        run.error_message = error_message[:4000]
        self._session.add(run)
        self._session.commit()

    def list_recent_failed(self, limit: int = 20) -> list[AgentRunORM]:
        stmt = (
            select(AgentRunORM)
            .where(AgentRunORM.status == AgentRunStatus.FAILED.value)
            .order_by(AgentRunORM.started_at.desc(), AgentRunORM.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_by_id(self, run_id: int) -> AgentRunORM | None:
        stmt = select(AgentRunORM).where(AgentRunORM.id == run_id)
        return self._session.execute(stmt).scalars().first()
