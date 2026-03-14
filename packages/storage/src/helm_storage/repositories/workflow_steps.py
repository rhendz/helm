from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import WorkflowStepORM
from helm_storage.repositories.contracts import NewWorkflowStep, WorkflowStepPatch


class SQLAlchemyWorkflowStepRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, step: NewWorkflowStep) -> WorkflowStepORM:
        record = WorkflowStepORM(
            run_id=step.run_id,
            step_name=step.step_name,
            status=step.status,
            attempt_number=step.attempt_number,
            validation_outcome_summary=step.validation_outcome_summary,
            execution_error_summary=step.execution_error_summary,
            failure_class=step.failure_class,
            retry_state=step.retry_state,
            retryable=step.retryable,
            completed_at=step.completed_at,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def update(self, step_id: int, patch: WorkflowStepPatch) -> WorkflowStepORM | None:
        record = self._get_by_id(step_id)
        if record is None:
            return None

        for field_name in WorkflowStepPatch.__dataclass_fields__:
            value = getattr(patch, field_name)
            if value is not None:
                setattr(record, field_name, value)

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def list_for_run(self, run_id: int) -> list[WorkflowStepORM]:
        stmt = (
            select(WorkflowStepORM)
            .where(WorkflowStepORM.run_id == run_id)
            .order_by(WorkflowStepORM.attempt_number.asc(), WorkflowStepORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_last_for_run(
        self, run_id: int, *, step_name: str | None = None
    ) -> WorkflowStepORM | None:
        stmt = select(WorkflowStepORM).where(WorkflowStepORM.run_id == run_id)
        if step_name is not None:
            stmt = stmt.where(WorkflowStepORM.step_name == step_name)
        stmt = stmt.order_by(WorkflowStepORM.attempt_number.desc(), WorkflowStepORM.id.desc())
        return self._session.execute(stmt).scalars().first()

    def get_last_failed_for_run(self, run_id: int) -> WorkflowStepORM | None:
        stmt = (
            select(WorkflowStepORM)
            .where(WorkflowStepORM.run_id == run_id)
            .where(WorkflowStepORM.status.in_(("failed", "validation_failed")))
            .order_by(WorkflowStepORM.completed_at.desc(), WorkflowStepORM.id.desc())
        )
        return self._session.execute(stmt).scalars().first()

    def _get_by_id(self, step_id: int) -> WorkflowStepORM | None:
        stmt = select(WorkflowStepORM).where(WorkflowStepORM.id == step_id)
        return self._session.execute(stmt).scalars().first()
