from sqlalchemy import func, select
from sqlalchemy.orm import Session

from helm_storage.models import WorkflowArtifactORM
from helm_storage.repositories.contracts import NewWorkflowArtifact


class SQLAlchemyWorkflowArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, artifact: NewWorkflowArtifact) -> WorkflowArtifactORM:
        version_number = artifact.version_number or self._next_version_number(
            run_id=artifact.run_id,
            artifact_type=artifact.artifact_type,
        )
        record = WorkflowArtifactORM(
            run_id=artifact.run_id,
            step_id=artifact.step_id,
            artifact_type=artifact.artifact_type,
            schema_version=artifact.schema_version,
            version_number=version_number,
            producer_step_name=artifact.producer_step_name,
            lineage_parent_id=artifact.lineage_parent_id,
            supersedes_artifact_id=artifact.supersedes_artifact_id,
            payload=artifact.payload,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def list_for_run(self, run_id: int) -> list[WorkflowArtifactORM]:
        stmt = (
            select(WorkflowArtifactORM)
            .where(WorkflowArtifactORM.run_id == run_id)
            .order_by(
                WorkflowArtifactORM.artifact_type.asc(),
                WorkflowArtifactORM.version_number.asc(),
                WorkflowArtifactORM.id.asc(),
            )
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_latest_for_run(
        self,
        run_id: int,
        *,
        artifact_type: str | None = None,
    ) -> WorkflowArtifactORM | None:
        stmt = select(WorkflowArtifactORM).where(WorkflowArtifactORM.run_id == run_id)
        if artifact_type is not None:
            stmt = stmt.where(WorkflowArtifactORM.artifact_type == artifact_type)
        stmt = stmt.order_by(WorkflowArtifactORM.created_at.desc(), WorkflowArtifactORM.id.desc())
        return self._session.execute(stmt).scalars().first()

    def get_latest_by_type(self, run_id: int) -> dict[str, WorkflowArtifactORM]:
        latest: dict[str, WorkflowArtifactORM] = {}
        for artifact in self.list_for_run(run_id):
            current = latest.get(artifact.artifact_type)
            if current is None or artifact.version_number > current.version_number:
                latest[artifact.artifact_type] = artifact
        return latest

    def _next_version_number(self, *, run_id: int, artifact_type: str) -> int:
        stmt = select(func.max(WorkflowArtifactORM.version_number)).where(
            WorkflowArtifactORM.run_id == run_id,
            WorkflowArtifactORM.artifact_type == artifact_type,
        )
        current = self._session.execute(stmt).scalar_one()
        return 1 if current is None else int(current) + 1
