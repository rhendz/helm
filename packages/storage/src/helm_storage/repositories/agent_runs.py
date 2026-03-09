from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import AgentRunORM


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
            status="running",
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
        run.status = "succeeded"
        run.completed_at = datetime.utcnow()
        run.error_message = None
        self._session.add(run)
        self._session.commit()

    def mark_failed(self, run_id: int, error_message: str) -> None:
        run = self.get_by_id(run_id)
        if run is None:
            return
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.error_message = error_message[:4000]
        self._session.add(run)
        self._session.commit()

    def list_recent_failed(self, limit: int = 20) -> list[AgentRunORM]:
        stmt = (
            select(AgentRunORM)
            .where(AgentRunORM.status == "failed")
            .order_by(AgentRunORM.started_at.desc(), AgentRunORM.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_by_id(self, run_id: int) -> AgentRunORM | None:
        stmt = select(AgentRunORM).where(AgentRunORM.id == run_id)
        return self._session.execute(stmt).scalars().first()
