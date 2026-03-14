from datetime import UTC, datetime
from json import dumps
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from helm_storage.models import WorkflowStepORM, WorkflowSyncRecordORM
from helm_storage.repositories.contracts import (
    NewWorkflowSyncRecord,
    WorkflowSyncFailedQuery,
    WorkflowSyncIdentityQuery,
    WorkflowSyncRecordPatch,
    WorkflowSyncRemainingQuery,
    WorkflowSyncRecoveryClassification,
    WorkflowSyncStatus,
    WorkflowSyncStepQuery,
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
            attempt_count=sync_record.attempt_count,
            last_attempt_step_id=sync_record.last_attempt_step_id,
            last_attempted_at=sync_record.last_attempted_at,
            completed_at=sync_record.completed_at,
            lineage_generation=sync_record.lineage_generation,
            recovery_classification=sync_record.recovery_classification,
            recovery_updated_at=sync_record.recovery_updated_at,
            replay_requested_at=sync_record.replay_requested_at,
            replay_requested_by=sync_record.replay_requested_by,
            terminated_at=sync_record.terminated_at,
            termination_reason=sync_record.termination_reason,
            terminated_after_sync_count=sync_record.terminated_after_sync_count,
            terminated_after_planned_item_key=sync_record.terminated_after_planned_item_key,
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
        stmt = (
            select(WorkflowSyncRecordORM)
            .where(
                WorkflowSyncRecordORM.proposal_artifact_id == proposal_artifact_id,
                WorkflowSyncRecordORM.proposal_version_number == proposal_version_number,
                WorkflowSyncRecordORM.target_system == target_system,
                WorkflowSyncRecordORM.sync_kind == sync_kind,
                WorkflowSyncRecordORM.planned_item_key == planned_item_key,
            )
            .order_by(
                WorkflowSyncRecordORM.lineage_generation.desc(), WorkflowSyncRecordORM.id.desc()
            )
        )
        return self._session.execute(stmt).scalars().first()

    def list_lineage(self, query: WorkflowSyncIdentityQuery) -> list[WorkflowSyncRecordORM]:
        stmt = (
            select(WorkflowSyncRecordORM)
            .where(
                WorkflowSyncRecordORM.proposal_artifact_id == query.proposal_artifact_id,
                WorkflowSyncRecordORM.proposal_version_number == query.proposal_version_number,
                WorkflowSyncRecordORM.target_system == query.target_system,
                WorkflowSyncRecordORM.sync_kind == query.sync_kind,
                WorkflowSyncRecordORM.planned_item_key == query.planned_item_key,
            )
            .order_by(
                WorkflowSyncRecordORM.lineage_generation.asc(), WorkflowSyncRecordORM.id.asc()
            )
        )
        return list(self._session.execute(stmt).scalars().all())

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

    def list_for_step_attempt(self, query: WorkflowSyncStepQuery) -> list[WorkflowSyncRecordORM]:
        source_step = aliased(WorkflowStepORM)
        stmt = (
            select(WorkflowSyncRecordORM)
            .join(source_step, WorkflowSyncRecordORM.step_id == source_step.id)
            .where(WorkflowSyncRecordORM.run_id == query.run_id)
            .where(WorkflowSyncRecordORM.status.in_(query.statuses))
            .where(source_step.step_name == query.step_name)
            .where(source_step.attempt_number <= query.max_attempt_number)
            .order_by(WorkflowSyncRecordORM.execution_order.asc(), WorkflowSyncRecordORM.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def claim_next_pending(
        self,
        *,
        run_id: int,
        step_id: int,
        step_name: str,
        step_attempt_number: int,
    ) -> WorkflowSyncRecordORM | None:
        pending = self.list_for_step_attempt(
            WorkflowSyncStepQuery(
                run_id=run_id,
                step_name=step_name,
                max_attempt_number=step_attempt_number,
                statuses=(
                    WorkflowSyncStatus.PENDING.value,
                    WorkflowSyncStatus.FAILED_RETRYABLE.value,
                    WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                ),
            )
        )
        if not pending:
            return None
        return self.mark_attempt_started(pending[0].id, step_id=step_id)

    def mark_attempt_started(
        self,
        sync_record_id: int,
        *,
        step_id: int,
        attempted_at: datetime | None = None,
    ) -> WorkflowSyncRecordORM | None:
        record = self.get_by_id(sync_record_id)
        if record is None:
            return None
        record.status = WorkflowSyncStatus.IN_PROGRESS.value
        record.last_attempt_step_id = step_id
        record.last_attempted_at = attempted_at or _now()
        record.last_error_summary = None
        record.completed_at = None
        record.recovery_updated_at = record.last_attempted_at
        record.attempt_count = record.attempt_count + 1
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def mark_succeeded(
        self,
        sync_record_id: int,
        *,
        external_object_id: str | None = None,
        completed_at: datetime | None = None,
    ) -> WorkflowSyncRecordORM | None:
        record = self.get_by_id(sync_record_id)
        if record is None:
            return None
        record.status = WorkflowSyncStatus.SUCCEEDED.value
        record.external_object_id = external_object_id
        record.last_error_summary = None
        record.completed_at = completed_at or _now()
        record.recovery_classification = None
        record.recovery_updated_at = _now()
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def mark_failed(
        self,
        sync_record_id: int,
        *,
        status: str,
        error_summary: str | None,
        completed_at: datetime | None = None,
        external_object_id: str | None = None,
        recovery_classification: str | None = None,
    ) -> WorkflowSyncRecordORM | None:
        return self.update(
            sync_record_id,
            WorkflowSyncRecordPatch(
                status=status,
                external_object_id=external_object_id,
                last_error_summary=error_summary,
                completed_at=completed_at or _now(),
                recovery_classification=recovery_classification,
                recovery_updated_at=_now(),
            ),
        )

    def mark_drift_detected(
        self,
        sync_record_id: int,
        *,
        live_fingerprint: str,
        field_diffs: dict[str, Any],
    ) -> WorkflowSyncRecordORM | None:
        """Mark a sync record as having detected drift between planned and live state.
        
        Stores the live fingerprint and field differences as drift metadata in 
        last_error_summary for inspection and debugging. Assigns TERMINAL_FAILURE
        recovery classification to enable operator-initiated replay recovery.
        
        Args:
            sync_record_id: ID of the sync record to mark as drifted
            live_fingerprint: The observed fingerprint of the live external state
            field_diffs: Mapping of field names to differences (before/after, reason, etc.)
            
        Returns:
            Updated WorkflowSyncRecordORM if found, None if not found
        """
        drift_metadata = {
            "live_fingerprint": live_fingerprint,
            "field_diffs": field_diffs,
        }
        return self.update(
            sync_record_id,
            WorkflowSyncRecordPatch(
                status=WorkflowSyncStatus.DRIFT_DETECTED.value,
                last_error_summary=dumps(drift_metadata),
                recovery_classification=WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value,
                completed_at=_now(),
                recovery_updated_at=_now(),
            ),
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


def _now() -> datetime:
    return datetime.now(UTC)
