"""Unit tests for TelegramWorkflowStatusService sync query methods."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from helm_storage.db import Base
from helm_storage.models import (
    WorkflowEventORM,
    WorkflowRunORM,
    WorkflowSyncRecordORM,
)
from helm_storage.repositories import (
    NewWorkflowEvent,
    NewWorkflowSyncRecord,
    WorkflowSyncStatus,
    WorkflowTargetSystem,
)
from helm_storage.repositories.workflow_events import SQLAlchemyWorkflowEventRepository
from helm_storage.repositories.workflow_sync_records import (
    SQLAlchemyWorkflowSyncRecordRepository,
)
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def test_session() -> Session:
    """Create an in-memory SQLite test database session."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def mock_sessionlocal(test_session: Session):
    """Mock SessionLocal to use the test session."""
    with patch("helm_telegram_bot.services.workflow_status_service.SessionLocal") as mock:
        mock.return_value.__enter__.return_value = test_session
        mock.return_value.__exit__.return_value = None
        yield mock


def _create_test_run(session: Session) -> WorkflowRunORM:
    """Create a minimal test workflow run."""
    run = WorkflowRunORM(
        workflow_type="weekly_scheduling",
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def test_list_sync_events_happy_path(test_session: Session, mock_sessionlocal) -> None:
    """Test list_sync_events returns properly-typed dicts with all expected fields."""
    # Setup: Create a workflow run and sync records
    run = _create_test_run(test_session)
    sync_repo = SQLAlchemyWorkflowSyncRecordRepository(test_session)

    sync_record_1 = sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
            sync_kind="create",
            planned_item_key="task_123",
            execution_order=1,
            status=WorkflowSyncStatus.SUCCEEDED.value,
            idempotency_key="idem_1",
            payload_fingerprint="fp_1",
            payload={"title": "Task 1"},
            external_object_id="ext_task_1",
        )
    )

    sync_record_2 = sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
            sync_kind="create",
            planned_item_key="event_456",
            execution_order=2,
            status=WorkflowSyncStatus.FAILED_RETRYABLE.value,
            idempotency_key="idem_2",
            payload_fingerprint="fp_2",
            payload={"title": "Event 1"},
            external_object_id=None,
            last_error_summary="Connection timeout",
        )
    )

    # Act: Call list_sync_events
    service = TelegramWorkflowStatusService()
    events = service.list_sync_events(run.id)

    # Assert
    assert len(events) == 2
    assert all(isinstance(e, dict) for e in events)

    # Check first event (most recent, sorted by created_at desc)
    # Since both were created ~immediately, order is determined by insertion
    event_1 = next((e for e in events if e["sync_record_id"] == sync_record_1.id), None)
    assert event_1 is not None
    assert event_1["planned_item_key"] == "task_123"
    assert event_1["status"] == "succeeded"
    assert event_1["external_object_id"] == "ext_task_1"
    assert event_1["created_at"] == sync_record_1.created_at
    assert event_1["last_error_summary"] is None
    assert event_1["drift_event"] is None

    event_2 = next((e for e in events if e["sync_record_id"] == sync_record_2.id), None)
    assert event_2 is not None
    assert event_2["planned_item_key"] == "event_456"
    assert event_2["status"] == "failed_retryable"
    assert event_2["external_object_id"] is None
    assert event_2["last_error_summary"] == "Connection timeout"
    assert event_2["drift_event"] is None


def test_list_sync_events_empty_results(test_session: Session, mock_sessionlocal) -> None:
    """Test list_sync_events returns empty list when no sync records exist."""
    run = _create_test_run(test_session)

    service = TelegramWorkflowStatusService()
    events = service.list_sync_events(run.id)

    assert events == []


def test_list_sync_events_with_drift_events(test_session: Session, mock_sessionlocal) -> None:
    """Test list_sync_events associates drift events correctly."""
    run = _create_test_run(test_session)
    sync_repo = SQLAlchemyWorkflowSyncRecordRepository(test_session)
    event_repo = SQLAlchemyWorkflowEventRepository(test_session)

    # Create a sync record
    sync_record = sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
            sync_kind="update",
            planned_item_key="event_789",
            execution_order=1,
            status=WorkflowSyncStatus.DRIFT_DETECTED.value,
            idempotency_key="idem_drift",
            payload_fingerprint="fp_drift",
            payload={"title": "Drifted Event"},
            external_object_id="ext_event_789",
        )
    )

    # Create a drift event associated with the sync record
    drift_event = event_repo.create(
        NewWorkflowEvent(
            run_id=run.id,
            step_id=1,
            event_type="drift_detected_external_change",
            summary="Event start time changed externally",
            details={
                "sync_record_id": sync_record.id,
                "field_diffs": {
                    "start": {"before": "2025-01-01 10:00", "after": "2025-01-01 14:00"}
                },
            },
        )
    )

    # Act
    service = TelegramWorkflowStatusService()
    events = service.list_sync_events(run.id)

    # Assert
    assert len(events) == 1
    event = events[0]
    assert event["sync_record_id"] == sync_record.id
    assert event["status"] == "drift_detected"
    assert event["drift_event"] is not None
    assert event["drift_event"]["event_id"] == drift_event.id
    assert event["drift_event"]["summary"] == "Event start time changed externally"
    assert "field_diffs" in event["drift_event"]["details"]


def test_list_sync_events_sorts_by_created_at_descending(test_session: Session, mock_sessionlocal) -> None:
    """Test list_sync_events sorts by created_at descending (most recent first)."""
    run = _create_test_run(test_session)
    sync_repo = SQLAlchemyWorkflowSyncRecordRepository(test_session)

    # Create records with explicit timestamps (descending)
    base_time = datetime.now(UTC)
    for i, offset_minutes in enumerate([10, 5, 0]):
        sync_repo.create(
            NewWorkflowSyncRecord(
                run_id=run.id,
                step_id=1,
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
                sync_kind="create",
                planned_item_key=f"task_{i}",
                execution_order=i,
                status=WorkflowSyncStatus.SUCCEEDED.value,
                idempotency_key=f"idem_{i}",
                payload_fingerprint=f"fp_{i}",
                payload={},
            )
        )

    # Act
    service = TelegramWorkflowStatusService()
    events = service.list_sync_events(run.id)

    # Assert: Events sorted by created_at descending
    assert len(events) == 3
    times = [e["created_at"] for e in events]
    assert times == sorted(times, reverse=True)


def test_get_sync_details_aggregates_counts(test_session: Session, mock_sessionlocal) -> None:
    """Test get_sync_details correctly aggregates sync counts."""
    run = _create_test_run(test_session)
    sync_repo = SQLAlchemyWorkflowSyncRecordRepository(test_session)

    # Create multiple sync records with different statuses and targets
    sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
            sync_kind="create",
            planned_item_key="task_1",
            execution_order=1,
            status=WorkflowSyncStatus.SUCCEEDED.value,
            idempotency_key="idem_1",
            payload_fingerprint="fp_1",
            payload={},
        )
    )

    sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
            sync_kind="create",
            planned_item_key="task_2",
            execution_order=2,
            status=WorkflowSyncStatus.SUCCEEDED.value,
            idempotency_key="idem_2",
            payload_fingerprint="fp_2",
            payload={},
        )
    )

    sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
            sync_kind="create",
            planned_item_key="event_1",
            execution_order=3,
            status=WorkflowSyncStatus.SUCCEEDED.value,
            idempotency_key="idem_3",
            payload_fingerprint="fp_3",
            payload={},
        )
    )

    # One failed record (should not be counted)
    sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
            sync_kind="create",
            planned_item_key="task_3",
            execution_order=4,
            status=WorkflowSyncStatus.FAILED_RETRYABLE.value,
            idempotency_key="idem_4",
            payload_fingerprint="fp_4",
            payload={},
        )
    )

    # Act
    service = TelegramWorkflowStatusService()
    details = service.get_sync_details(run.id)

    # Assert
    assert details["total_sync_writes"] == 3  # Only succeeded records
    assert details["task_sync_writes"] == 2  # Two task system succeeded
    assert details["calendar_sync_writes"] == 1  # One calendar system succeeded
    assert len(details["sync_records"]) == 4  # All records in timeline
    assert len(details["drift_events"]) == 0  # No drift events


def test_get_sync_details_empty_run(test_session: Session, mock_sessionlocal) -> None:
    """Test get_sync_details handles empty runs gracefully."""
    run = _create_test_run(test_session)

    service = TelegramWorkflowStatusService()
    details = service.get_sync_details(run.id)

    assert details["total_sync_writes"] == 0
    assert details["task_sync_writes"] == 0
    assert details["calendar_sync_writes"] == 0
    assert details["sync_records"] == []
    assert details["drift_events"] == []


def test_get_sync_details_with_drift_events(test_session: Session, mock_sessionlocal) -> None:
    """Test get_sync_details includes and formats drift events."""
    run = _create_test_run(test_session)
    sync_repo = SQLAlchemyWorkflowSyncRecordRepository(test_session)
    event_repo = SQLAlchemyWorkflowEventRepository(test_session)

    # Create a sync record
    sync_record = sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
            sync_kind="update",
            planned_item_key="event_drift",
            execution_order=1,
            status=WorkflowSyncStatus.DRIFT_DETECTED.value,
            idempotency_key="idem_drift",
            payload_fingerprint="fp_drift",
            payload={},
            external_object_id="ext_event",
        )
    )

    # Create two drift events
    event_1 = event_repo.create(
        NewWorkflowEvent(
            run_id=run.id,
            step_id=1,
            event_type="drift_detected_external_change",
            summary="Field changed",
            details={
                "sync_record_id": sync_record.id,
                "field": "start",
                "before": "10:00",
                "after": "11:00",
            },
        )
    )

    event_2 = event_repo.create(
        NewWorkflowEvent(
            run_id=run.id,
            step_id=1,
            event_type="drift_detected_external_change",
            summary="Another field changed",
            details={
                "sync_record_id": sync_record.id,
                "field": "title",
                "before": "Old Title",
                "after": "New Title",
            },
        )
    )

    # Act
    service = TelegramWorkflowStatusService()
    details = service.get_sync_details(run.id)

    # Assert
    assert len(details["drift_events"]) == 2
    drift_summaries = {e["summary"] for e in details["drift_events"]}
    assert drift_summaries == {"Field changed", "Another field changed"}

    # Verify drift event structure
    for drift in details["drift_events"]:
        assert "event_id" in drift
        assert "summary" in drift
        assert "details" in drift
        assert "created_at" in drift


def test_list_sync_events_missing_drift_record_id(test_session: Session, mock_sessionlocal) -> None:
    """Test list_sync_events handles drift events missing sync_record_id gracefully."""
    run = _create_test_run(test_session)
    sync_repo = SQLAlchemyWorkflowSyncRecordRepository(test_session)
    event_repo = SQLAlchemyWorkflowEventRepository(test_session)

    # Create a sync record
    sync_record = sync_repo.create(
        NewWorkflowSyncRecord(
            run_id=run.id,
            step_id=1,
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
            sync_kind="update",
            planned_item_key="event_xyz",
            execution_order=1,
            status=WorkflowSyncStatus.DRIFT_DETECTED.value,
            idempotency_key="idem_xyz",
            payload_fingerprint="fp_xyz",
            payload={},
        )
    )

    # Create a drift event WITHOUT sync_record_id in details
    event_repo.create(
        NewWorkflowEvent(
            run_id=run.id,
            step_id=1,
            event_type="drift_detected_external_change",
            summary="Drift detected but no sync_record_id",
            details={"field": "title", "before": "A", "after": "B"},
        )
    )

    # Act
    service = TelegramWorkflowStatusService()
    events = service.list_sync_events(run.id)

    # Assert: Sync record is still returned, drift_event is None
    assert len(events) == 1
    assert events[0]["sync_record_id"] == sync_record.id
    assert events[0]["drift_event"] is None
