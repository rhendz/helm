from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from helm_storage.models import (
    WorkflowApprovalCheckpointORM,
    WorkflowArtifactORM,
    WorkflowRunORM,
    WorkflowStepORM,
)
from helm_storage.repositories.contracts import WorkflowRunPatch, WorkflowRunState


class SQLAlchemyWorkflowRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, run) -> WorkflowRunORM:
        record = WorkflowRunORM(
            workflow_type=run.workflow_type,
            status=run.status,
            current_step_name=run.current_step_name,
            needs_action=run.needs_action,
            current_step_attempt=run.current_step_attempt,
            attempt_count=run.attempt_count,
            validation_outcome_summary=run.validation_outcome_summary,
            execution_error_summary=run.execution_error_summary,
            blocked_reason=run.blocked_reason,
            failure_class=run.failure_class,
            retry_state=run.retry_state,
            resume_step_name=run.resume_step_name,
            resume_step_attempt=run.resume_step_attempt,
            last_event_summary=run.last_event_summary,
            completed_at=run.completed_at,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_by_id(self, run_id: int) -> WorkflowRunORM | None:
        stmt = select(WorkflowRunORM).where(WorkflowRunORM.id == run_id)
        return self._session.execute(stmt).scalars().first()

    def update(self, run_id: int, patch: WorkflowRunPatch) -> WorkflowRunORM | None:
        record = self.get_by_id(run_id)
        if record is None:
            return None

        for field_name in WorkflowRunPatch.__dataclass_fields__:
            value = getattr(patch, field_name)
            if value is not None:
                setattr(record, field_name, value)

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_with_current_state(self, run_id: int) -> WorkflowRunState | None:
        stmt = (
            select(WorkflowRunORM)
            .options(
                selectinload(WorkflowRunORM.steps),
                selectinload(WorkflowRunORM.artifacts),
                selectinload(WorkflowRunORM.events),
                selectinload(WorkflowRunORM.approval_checkpoints),
                selectinload(WorkflowRunORM.sync_records),
            )
            .where(WorkflowRunORM.id == run_id)
        )
        run = self._session.execute(stmt).scalars().first()
        if run is None:
            return None
        return _build_state(run)

    def list_needing_action(self, *, limit: int | None = None) -> list[WorkflowRunState]:
        stmt = (
            select(WorkflowRunORM)
            .options(
                selectinload(WorkflowRunORM.steps),
                selectinload(WorkflowRunORM.artifacts),
                selectinload(WorkflowRunORM.events),
                selectinload(WorkflowRunORM.approval_checkpoints),
                selectinload(WorkflowRunORM.sync_records),
            )
            .where(WorkflowRunORM.needs_action.is_(True))
            .order_by(WorkflowRunORM.started_at.desc(), WorkflowRunORM.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        runs = self._session.execute(stmt).scalars().all()
        return [_build_state(run) for run in runs]

    def list_runnable(self, *, limit: int | None = None) -> list[WorkflowRunState]:
        stmt = (
            select(WorkflowRunORM)
            .options(
                selectinload(WorkflowRunORM.steps),
                selectinload(WorkflowRunORM.artifacts),
                selectinload(WorkflowRunORM.events),
                selectinload(WorkflowRunORM.approval_checkpoints),
                selectinload(WorkflowRunORM.sync_records),
            )
            .where(WorkflowRunORM.needs_action.is_(False))
            .where(WorkflowRunORM.status.in_(("pending", "running")))
            .order_by(WorkflowRunORM.started_at.asc(), WorkflowRunORM.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        runs = self._session.execute(stmt).scalars().all()
        return [_build_state(run) for run in runs]


def _build_state(run: WorkflowRunORM) -> WorkflowRunState:
    current_step = _pick_current_step(run.steps, run.current_step_name, run.current_step_attempt)
    latest_artifacts = _latest_artifacts(run.artifacts)
    last_event = max(run.events, key=lambda event: event.id) if run.events else None
    approval_checkpoints = tuple(sorted(run.approval_checkpoints, key=lambda checkpoint: checkpoint.id))
    active_approval_checkpoint = _pick_active_approval_checkpoint(approval_checkpoints)
    return WorkflowRunState(
        run=run,
        current_step=current_step,
        latest_artifacts=latest_artifacts,
        last_event=last_event,
        approval_checkpoints=approval_checkpoints,
        active_approval_checkpoint=active_approval_checkpoint,
        sync_records=tuple(sorted(run.sync_records, key=lambda sync_record: (sync_record.execution_order, sync_record.id))),
    )


def _pick_current_step(
    steps: list[WorkflowStepORM],
    current_step_name: str | None,
    current_step_attempt: int,
) -> WorkflowStepORM | None:
    if current_step_name is not None:
        matching = [
            step
            for step in steps
            if step.step_name == current_step_name and step.attempt_number == current_step_attempt
        ]
        if matching:
            return max(matching, key=lambda step: step.id)
    return max(steps, key=lambda step: step.id) if steps else None


def _latest_artifacts(artifacts: list[WorkflowArtifactORM]) -> dict[str, WorkflowArtifactORM]:
    latest: dict[str, WorkflowArtifactORM] = {}
    for artifact in artifacts:
        existing = latest.get(artifact.artifact_type)
        if existing is None or artifact.version_number > existing.version_number:
            latest[artifact.artifact_type] = artifact
    return latest


def _pick_active_approval_checkpoint(
    approval_checkpoints: tuple[WorkflowApprovalCheckpointORM, ...],
) -> WorkflowApprovalCheckpointORM | None:
    pending = [checkpoint for checkpoint in approval_checkpoints if checkpoint.status == "pending"]
    if pending:
        return max(pending, key=lambda checkpoint: checkpoint.id)
    return None
