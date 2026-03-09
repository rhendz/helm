from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from helm_storage.models import AgentRunORM


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class AgentRunCreate:
    agent_name: str
    source_type: str | None = None
    source_id: str | None = None


class AgentRunRepository(Protocol):
    def create(self, payload: AgentRunCreate) -> AgentRunORM: ...

    def get_by_id(self, run_id: int) -> AgentRunORM | None: ...

    def mark_succeeded(self, run_id: int) -> AgentRunORM | None: ...

    def mark_failed(self, run_id: int, *, error_message: str) -> AgentRunORM | None: ...

    def list_recent(self, *, limit: int = 20, status: str | None = None) -> list[AgentRunORM]: ...


class SQLAlchemyAgentRunRepository(AgentRunRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, payload: AgentRunCreate) -> AgentRunORM:
        run = AgentRunORM(
            agent_name=payload.agent_name,
            source_type=payload.source_type,
            source_id=payload.source_id,
            status="running",
            started_at=_utcnow(),
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def get_by_id(self, run_id: int) -> AgentRunORM | None:
        return self._session.get(AgentRunORM, run_id)

    def mark_succeeded(self, run_id: int) -> AgentRunORM | None:
        run = self.get_by_id(run_id)
        if run is None:
            return None
        run.status = "success"
        run.completed_at = _utcnow()
        run.error_message = None
        self._session.commit()
        self._session.refresh(run)
        return run

    def mark_failed(self, run_id: int, *, error_message: str) -> AgentRunORM | None:
        run = self.get_by_id(run_id)
        if run is None:
            return None
        run.status = "failed"
        run.completed_at = _utcnow()
        run.error_message = error_message
        self._session.commit()
        self._session.refresh(run)
        return run

    def list_recent(self, *, limit: int = 20, status: str | None = None) -> list[AgentRunORM]:
        stmt: Select[tuple[AgentRunORM]] = select(AgentRunORM)
        if status is not None:
            stmt = stmt.where(AgentRunORM.status == status)
        stmt = stmt.order_by(desc(AgentRunORM.started_at), desc(AgentRunORM.id)).limit(limit)
        return list(self._session.scalars(stmt).all())
