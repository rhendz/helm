"""Integration test for weekly scheduling end-to-end flow.

This test exercises the representative weekly scheduling / task+calendar workflow
through API and worker semantics:
1. Create a weekly scheduling workflow run via API
2. Advance through proposal generation via worker job functions
3. Assert on approval checkpoints and proposal artifacts
4. Approve the schedule and apply it
5. Assert on completion summary and sync records

The test serves as a primary automated guardrail for task/calendar workflows
after M002 cleanup and aligns with the UAT script in .gsd/milestones/M002/slices/S03/uat.md
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from helm_api.dependencies import get_db
from helm_api.main import app
from helm_api.services import replay_service
from helm_connectors import StubCalendarSystemAdapter, StubTaskSystemAdapter
from helm_orchestration import (
    NormalizedTaskValidator,
    RegisteredValidator,
    ScheduleProposalValidator,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowOrchestrationService,
)
from helm_storage.db import Base
from helm_storage.repositories import (
    SQLAlchemyWorkflowSyncRecordRepository,
    WorkflowArtifactType,
    WorkflowRunStatus,
    WorkflowTargetSystem,
)
from helm_worker.jobs import workflow_runs as workflow_runs_job
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class _SessionContext:
    """Context manager for test session that works with monkeypatch."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


def _validator_registry() -> ValidatorRegistry:
    """Build a minimal validator registry for workflow execution."""
    return ValidatorRegistry(
        [
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.STEP_NAME,
                    value="normalize_request",
                ),
                validator=NormalizedTaskValidator(),
            ),
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.ARTIFACT_TYPE,
                    value=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
                ),
                validator=ScheduleProposalValidator(),
            ),
        ]
    )


def _client() -> Generator[tuple[TestClient, Session], None, None]:
    """Pytest fixture providing in-memory test client and session."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()

    def _override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app), session
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_weekly_scheduling_end_to_end_happy_path(monkeypatch) -> None:  # noqa: ANN001
    """Test complete weekly scheduling workflow: create → proposal → approval → apply → sync.

    This test verifies the representative flow documented in the UAT script:
    1. Create a weekly scheduling run with representative task/constraint request
    2. Run worker to advance through dispatch_task_agent and dispatch_calendar_agent
    3. Verify run blocks at await_schedule_approval with approval checkpoint
    4. Assert on proposal artifacts and their linkage
    5. Approve the schedule
    6. Execute sync and verify completion summary
    7. Assert on sync records and their relationship to completion summary
    """
    for client, session in _client():
        # Monkeypatch worker to use test session
        monkeypatch.setattr(workflow_runs_job, "SessionLocal", lambda: _SessionContext(session))
        monkeypatch.setattr(replay_service, "SessionLocal", lambda: _SessionContext(session))

        # Set up real Google Calendar credentials to enable GoogleCalendarAdapter
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "test-refresh-token")

        # Step 1: Create a weekly scheduling run via API
        request_text = (
            "Plan my week. Tasks: Finish roadmap draft high due Wednesday 90m; "
            "Prep interviews medium 120m; Clear inbox low 30m. "
            "Constraints: protect deep work mornings; keep Friday afternoon open."
        )
        created = client.post(
            "/v1/workflow-runs",
            json={
                "workflow_type": "weekly_scheduling",
                "first_step_name": "dispatch_task_agent",
                "request_text": request_text,
                "submitted_by": "test-operator",
                "channel": "api",
            },
        )
        assert created.status_code == 200
        run_id = created.json()["id"]
        assert created.json()["status"] == WorkflowRunStatus.PENDING.value
        assert created.json()["workflow_type"] == "weekly_scheduling"
        assert created.json()["current_step"] == "dispatch_task_agent"

        # Step 2: Run worker to advance to proposal generation
        # First run: dispatch_task_agent -> completion
        # Second run: dispatch_calendar_agent -> completion and block at await_schedule_approval
        job_count_1 = workflow_runs_job.run(handlers=workflow_runs_job._build_specialist_steps())
        assert job_count_1 >= 1, "Worker should process at least one job (dispatch_task_agent)"

        job_count_2 = workflow_runs_job.run(handlers=workflow_runs_job._build_specialist_steps())
        assert job_count_2 >= 1, "Worker should process at least one job (dispatch_calendar_agent)"

        # Step 3: Verify run blocks at approval checkpoint
        blocked = client.get(f"/v1/workflow-runs/{run_id}")
        assert blocked.status_code == 200
        blocked_data = blocked.json()
        assert blocked_data["status"] == WorkflowRunStatus.BLOCKED.value
        assert blocked_data["paused_state"] == "awaiting_approval"
        assert blocked_data["current_step"] == "await_schedule_approval"
        assert blocked_data["needs_action"] is True

        # Step 4: Assert on approval checkpoint and proposal artifacts
        checkpoint = blocked_data["approval_checkpoint"]
        assert checkpoint is not None
        assert "target_artifact_id" in checkpoint
        target_artifact_id = checkpoint["target_artifact_id"]
        assert checkpoint["target_version_number"] == 1
        assert checkpoint["proposal_summary"] is not None
        assert len(checkpoint["proposal_summary"]) > 0
        assert checkpoint["allowed_actions"] == ["approve", "reject", "request_revision"]

        # Verify proposal exists via proposal-versions endpoint
        proposal_versions = client.get(f"/v1/workflow-runs/{run_id}/proposal-versions")
        assert proposal_versions.status_code == 200
        versions = proposal_versions.json()
        assert len(versions) > 0
        proposal = versions[0]
        assert proposal["artifact_id"] == target_artifact_id
        assert proposal["version_number"] == 1
        assert proposal["is_latest"] is True
        assert proposal["is_actionable"] is True
        assert proposal["approved"] is False
        assert "time_blocks" in proposal
        assert isinstance(proposal["time_blocks"], list)
        assert len(proposal["time_blocks"]) > 0  # Should have scheduled items
        assert "honored_constraints" in proposal
        assert isinstance(proposal["honored_constraints"], list)

        # Step 5: Approve the schedule
        approved = client.post(
            f"/v1/workflow-runs/{run_id}/approve",
            json={"actor": "test-operator", "target_artifact_id": target_artifact_id},
        )
        assert approved.status_code == 200
        approved_data = approved.json()
        assert approved_data["status"] == WorkflowRunStatus.PENDING.value
        assert approved_data["current_step"] == "apply_schedule"
        assert approved_data["paused_state"] is None

        # Step 6: Execute sync via orchestration service
        # Create service with real GoogleCalendarAdapter (credentials set via monkeypatch above)
        # Mock the Google Calendar API calls since we don't have real credentials
        from helm_connectors import GoogleCalendarAdapter, GoogleCalendarAuth

        # Mock the Credentials.refresh to avoid actual OAuth calls
        mock_credentials = MagicMock()
        mock_credentials.expired = False

        with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
            mock_creds_class.return_value = mock_credentials

            # Mock the Google Calendar API service
            mock_service = MagicMock()
            mock_events = MagicMock()
            mock_service.events.return_value = mock_events

            # Mock insert/update responses to return an event ID
            mock_insert = MagicMock()
            mock_insert.execute.return_value = {"id": "test-event-id-123"}
            mock_events.insert.return_value = mock_insert

            mock_update = MagicMock()
            mock_update.execute.return_value = {"id": "test-event-id-123"}
            mock_events.update.return_value = mock_update

            with patch("googleapiclient.discovery.build") as mock_build:
                mock_build.return_value = mock_service

                auth = GoogleCalendarAuth()
                orchestration = WorkflowOrchestrationService(
                    session,
                    validator_registry=_validator_registry(),
                    task_system_adapter=StubTaskSystemAdapter(),
                    calendar_system_adapter=GoogleCalendarAdapter(auth),
                )
                completed_result = orchestration.execute_pending_sync_step(run_id)
                assert completed_result.run.status == WorkflowRunStatus.COMPLETED.value
                
                # Capture source sync record IDs for later verification
                source_sync_records = SQLAlchemyWorkflowSyncRecordRepository(session).list_for_run(run_id)
                source_sync_record_ids = [
                    record.id
                    for record in source_sync_records
                    if record.replayed_from_sync_record_id is None
                ]
                assert len(source_sync_record_ids) > 0, "Should have created sync records"
                
                # Verify calendar sync records have external_object_id populated
                calendar_sync_records = [
                    r for r in source_sync_records
                    if r.target_system == WorkflowTargetSystem.CALENDAR_SYSTEM
                ]
                assert len(calendar_sync_records) > 0, "Should have calendar sync records"
                for record in calendar_sync_records:
                    assert record.external_object_id is not None, f"Calendar sync record {record.id} missing external_object_id"
                    assert record.external_object_id != "", f"Calendar sync record {record.id} has empty external_object_id"
        
        # Step 7: Assert on completion summary and sync records
        completed = client.get(f"/v1/workflow-runs/{run_id}")
        assert completed.status_code == 200
        completed_data = completed.json()
        assert completed_data["status"] == WorkflowRunStatus.COMPLETED.value
        assert completed_data["paused_state"] is None
        assert completed_data["needs_action"] is False
        
        # Verify completion summary
        completion_summary = completed_data["completion_summary"]
        assert completion_summary is not None
        assert "headline" in completion_summary
        assert len(completion_summary["headline"]) > 0
        assert completion_summary["approval_decision"] == "approve"
        assert completion_summary["downstream_sync_status"] == "succeeded"
        assert completion_summary["total_sync_writes"] > 0
        assert completion_summary["task_sync_writes"] > 0
        assert completion_summary["calendar_sync_writes"] > 0
        
        # Verify sync write counts match records
        total_sync_writes = (
            completion_summary["task_sync_writes"] + completion_summary["calendar_sync_writes"]
        )
        assert completion_summary["total_sync_writes"] == total_sync_writes
        
        # Verify lineage final summary has correct linkage
        final_summary = completed_data["lineage"]["final_summary"]
        assert final_summary is not None
        assert final_summary["approval_decision"] == "approve"
        assert final_summary["approval_decision_artifact_id"] is not None
        assert final_summary["approval_decision_artifact_id"] > 0
        assert final_summary["downstream_sync_status"] == "succeeded"
        assert "downstream_sync_reference_ids" in final_summary
        assert len(final_summary["downstream_sync_reference_ids"]) == len(source_sync_record_ids)


def test_weekly_scheduling_approval_checkpoint_blocks_execution(monkeypatch) -> None:  # noqa: ANN001
    """Test that workflow correctly blocks at approval checkpoint and requires action.

    Verifies that:
    - Workflow transitions to awaiting_approval state
    - Run.needs_action is true
    - available_actions are present
    - Workflow cannot proceed without approval
    """
    # Freeze scheduling "now" to a Sunday evening so all Mon-Fri slots generated
    # by compute_reference_week are in the future and past_event_guard never fires.
    from datetime import UTC, datetime as real_datetime
    from unittest.mock import patch as mock_patch

    _future_now = real_datetime(2099, 1, 5, 0, 1, 0, tzinfo=UTC)
    with mock_patch("helm_orchestration.scheduling.datetime") as mock_dt:
        mock_dt.now.return_value = _future_now
        mock_dt.side_effect = lambda *args, **kw: real_datetime(*args, **kw)

        for client, session in _client():
            monkeypatch.setattr(workflow_runs_job, "SessionLocal", lambda: _SessionContext(session))

            # Create run and advance to approval
            created = client.post(
                "/v1/workflow-runs",
                json={
                    "workflow_type": "weekly_scheduling",
                    "first_step_name": "dispatch_task_agent",
                    "request_text": "Plan my week. Tasks: Task 1 high 90m; Task 2 medium 60m. Constraints: protect mornings.",
                    "submitted_by": "test-operator",
                    "channel": "api",
                },
            )
            run_id = created.json()["id"]

            # Advance to approval checkpoint
            workflow_runs_job.run(handlers=workflow_runs_job._build_specialist_steps())
            workflow_runs_job.run(handlers=workflow_runs_job._build_specialist_steps())

            # Verify run is blocked and needs action
            blocked = client.get(f"/v1/workflow-runs/{run_id}")
            assert blocked.json()["paused_state"] == "awaiting_approval"
            assert blocked.json()["needs_action"] is True
            available_actions = blocked.json()["available_actions"]
            action_names = [a["action"] for a in available_actions]
            assert set(action_names) == {"approve", "reject", "request_revision"}

            # Verify no further progress without approval
            further_runs = workflow_runs_job.run(handlers=workflow_runs_job._build_specialist_steps())
            assert further_runs == 0, "Worker should not process any jobs when awaiting approval"

            still_blocked = client.get(f"/v1/workflow-runs/{run_id}")
            assert still_blocked.json()["paused_state"] == "awaiting_approval"


def test_weekly_scheduling_sync_record_integrity(monkeypatch) -> None:  # noqa: ANN001
    """Test that sync records are created correctly and linked to approval decision.

    Verifies that:
    - Sync records exist for both task and calendar writes
    - Each sync record has correct system_kind, target_system, and status
    - Sync records are linked to the workflow run
    - sync_artifact_id is populated in final summary
    """
    for client, session in _client():
        monkeypatch.setattr(workflow_runs_job, "SessionLocal", lambda: _SessionContext(session))
        monkeypatch.setattr(replay_service, "SessionLocal", lambda: _SessionContext(session))

        # Create and complete run
        created = client.post(
            "/v1/workflow-runs",
            json={
                "workflow_type": "weekly_scheduling",
                "first_step_name": "dispatch_task_agent",
                "request_text": "Plan: Task 1 high 120m; Task 2 med 90m; Task 3 low 45m.",
                "submitted_by": "test-operator",
                "channel": "api",
            },
        )
        run_id = created.json()["id"]

        # Advance to approval
        workflow_runs_job.run(handlers=workflow_runs_job._build_specialist_steps())
        workflow_runs_job.run(handlers=workflow_runs_job._build_specialist_steps())

        # Get approval details
        blocked = client.get(f"/v1/workflow-runs/{run_id}")
        target_artifact_id = blocked.json()["approval_checkpoint"]["target_artifact_id"]

        # Approve and execute sync
        client.post(
            f"/v1/workflow-runs/{run_id}/approve",
            json={"actor": "test-operator", "target_artifact_id": target_artifact_id},
        )

        orchestration = WorkflowOrchestrationService(
            session,
            validator_registry=_validator_registry(),
            task_system_adapter=StubTaskSystemAdapter(),
            calendar_system_adapter=StubCalendarSystemAdapter(),
        )
        orchestration.execute_pending_sync_step(run_id)

        # Verify sync records
        sync_records = SQLAlchemyWorkflowSyncRecordRepository(session).list_for_run(run_id)
        assert len(sync_records) > 0, "Should have sync records"

        # Verify both task and calendar syncs exist
        task_syncs = [r for r in sync_records if r.sync_kind == "task_upsert"]
        calendar_syncs = [r for r in sync_records if r.sync_kind == "calendar_block_upsert"]
        assert len(task_syncs) > 0, "Should have task sync records"
        assert len(calendar_syncs) > 0, "Should have calendar sync records"

        # Verify all syncs have succeeded status
        for record in sync_records:
            assert record.status == "succeeded"
            assert record.target_system in ["task_system", "calendar_system"]
            assert record.run_id == run_id

        # Verify completion summary reflects sync counts correctly
        completed = client.get(f"/v1/workflow-runs/{run_id}")
        completion = completed.json()["completion_summary"]
        assert completion["task_sync_writes"] == len(task_syncs)
        assert completion["calendar_sync_writes"] == len(calendar_syncs)
        assert completion["total_sync_writes"] == len(sync_records)
