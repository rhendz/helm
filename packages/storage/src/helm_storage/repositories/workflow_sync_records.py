from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import WorkflowSyncRecordORM
from helm_storage.repositories.contracts import (
    NewWorkflowSyncRecord,
    WorkflowSyncClaimPatch,
    WorkflowSyncFailedQuery,
    WorkflowSyncRecordPatch,
    WorkflowSyncRemainingQuery,
    WorkflowSyncStatus,
)


class SQLAlchemyWorkflowSyncRecordRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, sync_record: NewWorkflowSyncRecord) -> WorkflowSyncRecordORM:
        record = WorkflowSyncRecordORM(
            run_id=sync_record.run_id,
            step_id=sync_record.step_id,
            proposal_artifact_id=sync_record.proposal_artifact_id,
            proposal_version_number=sync_record.proposal_version_number,
            target_system=sync_record.target_system,
            sync_kind=sync_record.sync_kind,
            planned_item_key=sync_record.planned_item_key,
            execution_order=sync_record.execution_order,
            status=sync_record.status,
            idempotency_key=sync_record.idempotency_key,
            payload_fingerprint=sync_record.payload_fingerprint,
            payload=sync_record.payload,
            external_object_id=sync_record.external_object_id,
            last_error_summary=sync_record.last_error_summary,
            last_attempted_at=sync_record.last_attempted_at,
            completed_at=sync_record.completed_at,
            supersedes_sync_record_id=sync_record.supersedes_sync_record_id,
            replayed_from_sync_record_id=sync_record.replayed_from_sync_record_id,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_by_id(self, sync_record_id: int) -> WorkflowSyncRecordORM | None:
        stmt = select(WorkflowSyncRecordORM).where(WorkflowSyncRecordORM.id == sync_record_id)
        return self._session.execute(stmt).scalars().first()

    def get_by_identity(
        self,
        *,
        proposal_artifact_id: int,
        proposal_version_number: int,
        target_system: str,
        sync_kind: str,
        planned_item_key: str,
    ) -> WorkflowSyncRecordORM | None:
        stmt = select(WorkflowSyncRecordORM).where(
            WorkflowSyncRecordORM.proposal_artifact_id == proposal_artifact_id,
            WorkflowSyncRecordORM.proposal_version_number == proposal_version_number,
            WorkflowSyncRecordORM.target_system == target_system,
            WorkflowSyncRecordORM.sync_kind == sync_kind,
            WorkflowSyncRecordORM.planned_item_key == planned_item_key,
        )
        return self._session.execute(stmt).scalars().first()

    def list_for_run(self, run_id: int) -> list[WorkflowSyncRecordORM]:
        stmt = (
            select(WorkflowSyncRecordORM)
            .where(WorkflowSyncRecordORM.run_id == run_id)
            .order_by(WorkflowSyncRecordORM.execution_order.asc(), WorkflowSyncRecordORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_for_proposal(self, proposal_artifact_id: int) -> list[WorkflowSyncRecordORM]:
        stmt = (
            select(WorkflowSyncRecordORM)
            .where(WorkflowSyncRecordORM.proposal_artifact_id == proposal_artifact_id)
            .order_by(WorkflowSyncRecordORM.execution_order.asc(), WorkflowSyncRecordORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_remaining(self, query: WorkflowSyncRemainingQuery) -> list[WorkflowSyncRecordORM]:
        stmt = (
            select(WorkflowSyncRecordORM)
            .where(WorkflowSyncRecordORM.run_id == query.run_id)
            .where(WorkflowSyncRecordORM.status.in_(query.statuses))
            .order_by(WorkflowSyncRecordORM.execution_order.asc(), WorkflowSyncRecordORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_failed(self, query: WorkflowSyncFailedQuery) -> list[WorkflowSyncRecordORM]:
        stmt = (
            select(WorkflowSyncRecordORM)
            .where(WorkflowSyncRecordORM.run_id == query.run_id)
            .where(WorkflowSyncRecordORM.status.in_(query.statuses))
            .order_by(WorkflowSyncRecordORM.execution_order.asc(), WorkflowSyncRecordORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def claim_next_pending(self, *, run_id: int, step_id: int) -> WorkflowSyncRecordORM | None:
        pending = self.list_remaining(WorkflowSyncRemainingQuery(run_id=run_id))
        if not pending:
            return None
        next_record = pending[0]
        return self._apply_claim(
            next_record.id,
            WorkflowSyncClaimPatch(status=WorkflowSyncStatus.IN_PROGRESS.value),
            step_id=step_id,
        )

    def update(
        self,
        sync_record_id: int,
        patch: WorkflowSyncRecordPatch,
    ) -> WorkflowSyncRecordORM | None:
        record = self.get_by_id(sync_record_id)
        if record is None:
            return None
        for field_name in WorkflowSyncRecordPatch.__dataclass_fields__:
            value = getattr(patch, field_name)
            if value is not None:
                setattr(record, field_name, value)
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def _apply_claim(
        self,
        sync_record_id: int,
        patch: WorkflowSyncClaimPatch,
        *,
        step_id: int,
    ) -> WorkflowSyncRecordORM | None:
        record = self.get_by_id(sync_record_id)
        if record is None:
            return None
        record.step_id = step_id
        record.status = patch.status
        record.last_attempted_at = patch.last_attempted_at
        record.last_error_summary = patch.last_error_summary
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record
