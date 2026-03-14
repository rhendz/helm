from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import WorkflowEventORM
from helm_storage.repositories.contracts import NewWorkflowEvent


class SQLAlchemyWorkflowEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, event: NewWorkflowEvent) -> WorkflowEventORM:
        record = WorkflowEventORM(
            run_id=event.run_id,
            step_id=event.step_id,
            event_type=event.event_type,
            run_status=event.run_status,
            step_status=event.step_status,
            summary=event.summary,
            details=event.details or {},
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def list_for_run(self, run_id: int) -> list[WorkflowEventORM]:
        stmt = (
            select(WorkflowEventORM)
            .where(WorkflowEventORM.run_id == run_id)
            .order_by(WorkflowEventORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_for_run_by_type(self, run_id: int, *, event_type: str) -> list[WorkflowEventORM]:
        stmt = (
            select(WorkflowEventORM)
            .where(
                WorkflowEventORM.run_id == run_id,
                WorkflowEventORM.event_type == event_type,
            )
            .order_by(WorkflowEventORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())
