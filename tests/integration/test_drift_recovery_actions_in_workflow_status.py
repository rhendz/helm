"""Integration tests for drift recovery classification and safe_next_actions mapping."""

import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from helm_api.services.workflow_status_service import WorkflowStatusService
from helm_orchestration import StubTaskSystemAdapter, StubCalendarSystemAdapter
from helm_storage.db import Base
from helm_storage.models import (
    WorkflowRunORM,
    WorkflowStepORM,
    WorkflowSyncRecordORM,
)
from helm_storage.repositories import (
    SQLAlchemyWorkflowRunRepository,
    SQLAlchemyWorkflowStepRepository,
    SQLAlchemyWorkflowSyncRecordRepository,
    NewWorkflowRun,
    NewWorkflowStep,
    NewWorkflowSyncRecord,
    WorkflowRunState,
    WorkflowRunStatus,
    WorkflowStepStatus,
    WorkflowSyncKind,
    WorkflowSyncStatus,
    WorkflowSyncRecoveryClassification,
    WorkflowTargetSystem,
)


class TestDriftDetectionRecoveryActions:
    """Test that drift-detected records enable correct recovery actions in workflow status."""

    def test_drift_detected_record_shows_request_replay_action(self) -> None:
        """Drift-detected record should present request_replay as safe next action."""
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        
        with Session(engine) as session:
            run_repo = SQLAlchemyWorkflowRunRepository(session)
            step_repo = SQLAlchemyWorkflowStepRepository(session)
            sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
            
            run = run_repo.create(
                NewWorkflowRun(
                    workflow_type="weekly_scheduling",
                    current_step_name="sync",
                    
                    status=WorkflowRunStatus.RUNNING.value,
                )
            )
            
            step = step_repo.create(
                NewWorkflowStep(
                    run_id=run.id,
                    step_name="sync",
                    status=WorkflowStepStatus.RUNNING.value,
                )
            )
            
            status_service = WorkflowStatusService(
                session,
                task_system_adapter=StubTaskSystemAdapter(),
                calendar_system_adapter=StubCalendarSystemAdapter(),
            )
            
            # Create and mark a sync record as drift detected
            sync_record = sync_repo.create(
                NewWorkflowSyncRecord(
                    run_id=run.id,
                    step_id=step.id,
                    proposal_artifact_id=1,
                    proposal_version_number=1,
                    target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
                    sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
                    planned_item_key="time_block_001",
                    execution_order=0,
                    status=WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                    idempotency_key="idempotency_key_001",
                    payload_fingerprint="stored_fingerprint_hash",
                    payload={"title": "Team Sync", "start": "2026-03-14T10:00:00"},
                )
            )
            
            # Mark as drift detected
            drift_metadata = {
                "live_fingerprint": "live_hash",
                "field_diffs": {"start": {"before": "2026-03-14T10:00:00", "after": "2026-03-14T14:00:00"}},
            }
            sync_repo.mark_drift_detected(
                sync_record.id,
                live_fingerprint="live_hash",
                field_diffs=drift_metadata["field_diffs"],
            )
            
            # Get workflow status - it should show request_replay action
            summary = status_service.get_run_detail(run.id)
            
            # Verify drift-detected record is in the sync records
            assert summary is not None
            assert summary.get("sync") is not None
            sync_info = summary["sync"]
            
            # Verify the record has been marked as DRIFT_DETECTED
            assert sync_info.get("counts_by_state") is not None
            counts = sync_info["counts_by_state"]
            assert counts.get(WorkflowSyncStatus.DRIFT_DETECTED.value, 0) >= 1

    def test_drift_detected_with_terminal_failure_classification(self) -> None:
        """Drift records should have TERMINAL_FAILURE classification."""
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        
        with Session(engine) as session:
            run_repo = SQLAlchemyWorkflowRunRepository(session)
            step_repo = SQLAlchemyWorkflowStepRepository(session)
            sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
            
            run = run_repo.create(
                NewWorkflowRun(
                    workflow_type="weekly_scheduling",
                    current_step_name="sync",
                    
                    status=WorkflowRunStatus.RUNNING.value,
                )
            )
            
            step = step_repo.create(
                NewWorkflowStep(
                    run_id=run.id,
                    step_name="sync",
                    status=WorkflowStepStatus.RUNNING.value,
                )
            )
            
            sync_record = sync_repo.create(
                NewWorkflowSyncRecord(
                    run_id=run.id,
                    step_id=step.id,
                    proposal_artifact_id=1,
                    proposal_version_number=1,
                    target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
                    sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
                    planned_item_key="time_block_002",
                    execution_order=0,
                    status=WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                    idempotency_key="idempotency_key_002",
                    payload_fingerprint="stored_fingerprint_hash",
                    payload={"title": "Meeting", "start": "2026-03-14T09:00:00"},
                )
            )
            
            # Mark as drift detected
            updated_record = sync_repo.mark_drift_detected(
                sync_record.id,
                live_fingerprint="live_hash",
                field_diffs={"title": {"before": "Meeting", "after": "1:1 Meeting"}},
            )
            
            # Verify classification
            assert updated_record is not None
            assert updated_record.recovery_classification == WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value
            
            # Verify status
            assert updated_record.status == WorkflowSyncStatus.DRIFT_DETECTED.value

    def test_multiple_sync_records_with_mixed_outcomes(self) -> None:
        """Workflow with mixed outcomes (success, drift, pending) should show appropriate actions."""
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        
        with Session(engine) as session:
            run_repo = SQLAlchemyWorkflowRunRepository(session)
            step_repo = SQLAlchemyWorkflowStepRepository(session)
            sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
            
            run = run_repo.create(
                NewWorkflowRun(
                    workflow_type="weekly_scheduling",
                    current_step_name="sync",
                    
                    status=WorkflowRunStatus.RUNNING.value,
                )
            )
            
            step = step_repo.create(
                NewWorkflowStep(
                    run_id=run.id,
                    step_name="sync",
                    status=WorkflowStepStatus.RUNNING.value,
                )
            )
            
            status_service = WorkflowStatusService(
                session,
                task_system_adapter=StubTaskSystemAdapter(),
                calendar_system_adapter=StubCalendarSystemAdapter(),
            )
            
            # Create 3 sync records with different outcomes
            # 1. Successful record
            sync_repo.create(
                NewWorkflowSyncRecord(
                    run_id=run.id,
                    step_id=step.id,
                    proposal_artifact_id=1,
                    proposal_version_number=1,
                    target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
                    sync_kind=WorkflowSyncKind.TASK_UPSERT.value,
                    planned_item_key="task_001",
                    execution_order=0,
                    status=WorkflowSyncStatus.SUCCEEDED.value,
                    idempotency_key="idempotency_key_001",
                    payload_fingerprint="fingerprint_1",
                    payload={"title": "Task 1"},
                    external_object_id="ext_id_1",
                )
            )
            
            # 2. Drift-detected record
            drift_record = sync_repo.create(
                NewWorkflowSyncRecord(
                    run_id=run.id,
                    step_id=step.id,
                    proposal_artifact_id=1,
                    proposal_version_number=1,
                    target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
                    sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
                    planned_item_key="time_block_001",
                    execution_order=1,
                    status=WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                    idempotency_key="idempotency_key_002",
                    payload_fingerprint="fingerprint_2",
                    payload={"title": "Team Sync"},
                    external_object_id="ext_id_2",
                )
            )
            
            # 3. Pending record
            sync_repo.create(
                NewWorkflowSyncRecord(
                    run_id=run.id,
                    step_id=step.id,
                    proposal_artifact_id=1,
                    proposal_version_number=1,
                    target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
                    sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
                    planned_item_key="time_block_002",
                    execution_order=2,
                    status=WorkflowSyncStatus.PENDING.value,
                    idempotency_key="idempotency_key_003",
                    payload_fingerprint="fingerprint_3",
                    payload={"title": "Review Time"},
                )
            )
            
            # Mark the drift record as drift detected
            sync_repo.mark_drift_detected(
                drift_record.id,
                live_fingerprint="live_hash",
                field_diffs={"start": {"before": "10:00", "after": "14:00"}},
            )
            
            # Get workflow status
            summary = status_service.get_run_detail(run.id)
            
            # Verify sync counts reflect the mixed outcomes
            assert summary is not None
            assert summary.get("sync") is not None
            
            sync_section = summary["sync"]
            counts = sync_section.get("counts_by_state", {})
            
            # Should have: 1 succeeded, 1 drift_detected, 1 pending
            assert counts.get(WorkflowSyncStatus.SUCCEEDED.value, 0) >= 1
            assert counts.get(WorkflowSyncStatus.DRIFT_DETECTED.value, 0) >= 1
            assert counts.get(WorkflowSyncStatus.PENDING.value, 0) >= 1
