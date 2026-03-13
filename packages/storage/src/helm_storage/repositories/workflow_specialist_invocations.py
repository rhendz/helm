from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import WorkflowSpecialistInvocationORM
from helm_storage.repositories.contracts import (
    NewWorkflowSpecialistInvocation,
    WorkflowSpecialistInvocationPatch,
)


class SQLAlchemyWorkflowSpecialistInvocationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, invocation: NewWorkflowSpecialistInvocation) -> WorkflowSpecialistInvocationORM:
        record = WorkflowSpecialistInvocationORM(
            run_id=invocation.run_id,
            step_id=invocation.step_id,
            specialist_name=invocation.specialist_name,
            input_artifact_id=invocation.input_artifact_id,
            output_artifact_id=invocation.output_artifact_id,
            status=invocation.status,
            completed_at=invocation.completed_at,
            error_summary=invocation.error_summary,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def update(
        self,
        invocation_id: int,
        patch: WorkflowSpecialistInvocationPatch,
    ) -> WorkflowSpecialistInvocationORM | None:
        record = self._get_by_id(invocation_id)
        if record is None:
            return None

        for field_name in WorkflowSpecialistInvocationPatch.__dataclass_fields__:
            value = getattr(patch, field_name)
            if value is not None:
                setattr(record, field_name, value)

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def list_for_run(self, run_id: int) -> list[WorkflowSpecialistInvocationORM]:
        stmt = (
            select(WorkflowSpecialistInvocationORM)
            .where(WorkflowSpecialistInvocationORM.run_id == run_id)
            .order_by(
                WorkflowSpecialistInvocationORM.started_at.asc(),
                WorkflowSpecialistInvocationORM.id.asc(),
            )
        )
        return list(self._session.execute(stmt).scalars().all())

    def _get_by_id(self, invocation_id: int) -> WorkflowSpecialistInvocationORM | None:
        stmt = select(WorkflowSpecialistInvocationORM).where(
            WorkflowSpecialistInvocationORM.id == invocation_id
        )
        return self._session.execute(stmt).scalars().first()
