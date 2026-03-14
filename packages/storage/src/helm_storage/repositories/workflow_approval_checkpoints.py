from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import WorkflowApprovalCheckpointORM
from helm_storage.repositories.contracts import (
    NewWorkflowApprovalCheckpoint,
    WorkflowApprovalCheckpointPatch,
)


class SQLAlchemyWorkflowApprovalCheckpointRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, checkpoint: NewWorkflowApprovalCheckpoint) -> WorkflowApprovalCheckpointORM:
        record = WorkflowApprovalCheckpointORM(
            run_id=checkpoint.run_id,
            step_id=checkpoint.step_id,
            target_artifact_id=checkpoint.target_artifact_id,
            resume_step_name=checkpoint.resume_step_name,
            resume_step_attempt=checkpoint.resume_step_attempt,
            allowed_actions=list(checkpoint.allowed_actions),
            status=checkpoint.status,
            decision=checkpoint.decision,
            decision_actor=checkpoint.decision_actor,
            decision_at=checkpoint.decision_at,
            revision_feedback=checkpoint.revision_feedback,
            resolved_at=checkpoint.resolved_at,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def update(
        self,
        checkpoint_id: int,
        patch: WorkflowApprovalCheckpointPatch,
    ) -> WorkflowApprovalCheckpointORM | None:
        record = self.get_by_id(checkpoint_id)
        if record is None:
            return None

        for field_name in WorkflowApprovalCheckpointPatch.__dataclass_fields__:
            value = getattr(patch, field_name)
            if value is not None:
                setattr(record, field_name, value)

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_by_id(self, checkpoint_id: int) -> WorkflowApprovalCheckpointORM | None:
        stmt = select(WorkflowApprovalCheckpointORM).where(
            WorkflowApprovalCheckpointORM.id == checkpoint_id
        )
        return self._session.execute(stmt).scalars().first()

    def get_active_for_run(self, run_id: int) -> WorkflowApprovalCheckpointORM | None:
        stmt = (
            select(WorkflowApprovalCheckpointORM)
            .where(
                WorkflowApprovalCheckpointORM.run_id == run_id,
                WorkflowApprovalCheckpointORM.status == "pending",
            )
            .order_by(WorkflowApprovalCheckpointORM.id.desc())
        )
        return self._session.execute(stmt).scalars().first()

    def list_for_run(self, run_id: int) -> list[WorkflowApprovalCheckpointORM]:
        stmt = (
            select(WorkflowApprovalCheckpointORM)
            .where(WorkflowApprovalCheckpointORM.run_id == run_id)
            .order_by(WorkflowApprovalCheckpointORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())
