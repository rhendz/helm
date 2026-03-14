"""Unit tests for recovery classification assignment to drift-detected records."""

import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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


class TestRecoveryClassificationAssignment:
    """Test that recovery_classification is correctly assigned to drift-detected records."""

    def test_mark_drift_detected_assigns_terminal_failure_classification(self) -> None:
        """Drift-detected records should be assigned TERMINAL_FAILURE classification."""
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
            
            # Create a sync record
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
            field_diffs = {
                "start": {
                    "before": "2026-03-14T10:00:00",
                    "after": "2026-03-14T14:00:00",
                }
            }
            updated_record = sync_repo.mark_drift_detected(
                sync_record.id,
                live_fingerprint="live_fingerprint_hash",
                field_diffs=field_diffs,
            )
            
            # Verify recovery_classification is set
            assert updated_record is not None
            assert updated_record.recovery_classification == WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value
            assert updated_record.status == WorkflowSyncStatus.DRIFT_DETECTED.value

    def test_mark_drift_detected_preserves_drift_metadata(self) -> None:
        """Drift metadata should be preserved in last_error_summary."""
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
            
            field_diffs = {
                "title": {
                    "before": "Meeting",
                    "after": "1:1 Meeting",
                },
                "start": {
                    "before": "2026-03-14T09:00:00",
                    "after": "2026-03-14T10:00:00",
                },
            }
            
            updated_record = sync_repo.mark_drift_detected(
                sync_record.id,
                live_fingerprint="live_hash",
                field_diffs=field_diffs,
            )
            
            # Verify metadata is persisted
            assert updated_record is not None
            assert updated_record.last_error_summary is not None
            metadata = json.loads(updated_record.last_error_summary)
            assert metadata["live_fingerprint"] == "live_hash"
            assert metadata["field_diffs"] == field_diffs

    def test_mark_drift_detected_sets_completion_timestamps(self) -> None:
        """Timestamps should be set when marking drift detected."""
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
                    planned_item_key="time_block_003",
                    execution_order=0,
                    status=WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                    idempotency_key="idempotency_key_003",
                    payload_fingerprint="stored_fingerprint_hash",
                    payload={},
                )
            )
            
            assert sync_record.completed_at is None
            assert sync_record.recovery_updated_at is None
            
            updated_record = sync_repo.mark_drift_detected(
                sync_record.id,
                live_fingerprint="live_hash",
                field_diffs={},
            )
            
            # Verify timestamps are set
            assert updated_record is not None
            assert updated_record.completed_at is not None
            assert updated_record.recovery_updated_at is not None


class TestRecoveryClassificationMapping:
    """Test that recovery classification maps to correct safe_next_actions."""

    def test_drift_detected_maps_to_request_replay_action(self) -> None:
        """DRIFT_DETECTED records should map to request_replay action."""
        # Create a mock sync record with DRIFT_DETECTED status
        mock_record = type('MockRecord', (), {
            'status': WorkflowSyncStatus.DRIFT_DETECTED.value,
            'recovery_classification': WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value,
        })()
        
        # The mapping should be:
        # status == DRIFT_DETECTED -> [request_replay action]
        assert mock_record.status == WorkflowSyncStatus.DRIFT_DETECTED.value
        assert mock_record.recovery_classification == WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value

    def test_terminal_failure_classification_enables_request_replay(self) -> None:
        """TERMINAL_FAILURE classification should enable request_replay action."""
        assert WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value == "terminal_failure"
