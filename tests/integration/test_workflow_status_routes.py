from collections.abc import Generator

from fastapi.testclient import TestClient
from helm_api.dependencies import get_db
from helm_api.main import app
from helm_orchestration import (
    ExecutionFailurePayload,
    NormalizedTaskValidator,
    RegisteredValidator,
    RetryState,
    ScheduleProposalValidator,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowOrchestrationService,
)
from helm_storage.db import Base
from helm_storage.repositories import (
    NewWorkflowArtifact,
    SQLAlchemyWorkflowArtifactRepository,
    WorkflowArtifactType,
    WorkflowRunStatus,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _service(session: Session) -> WorkflowOrchestrationService:
    return WorkflowOrchestrationService(
        session,
        validator_registry=ValidatorRegistry(
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
        ),
    )


def _request_payload() -> dict[str, object]:
    return {
        "request_text": "Plan my week.",
        "submitted_by": "telegram:user",
        "channel": "telegram",
        "metadata": {"chat_id": "123"},
    }


def _normalized_payload() -> dict[str, object]:
    return {
        "title": "Weekly planning",
        "summary": "Focus on deep work.",
        "tasks": [{"title": "Deep work", "summary": "Plan", "priority": "high", "estimated_minutes": 90}],
    }


def _seed_states(session: Session) -> dict[str, int]:
    orchestration = _service(session)
    artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)

    running = orchestration.create_run(
        workflow_type="weekly_digest",
        first_step_name="normalize_request",
        request_payload=_request_payload(),
    )
    running = orchestration.complete_current_step(
        running.run.id,
        artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
        artifact_payload=_normalized_payload(),
        next_step_name="summarize",
    )

    blocked = orchestration.create_run(
        workflow_type="weekly_digest",
        first_step_name="normalize_request",
        request_payload=_request_payload(),
    )
    orchestration.complete_current_step(
        blocked.run.id,
        artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
        artifact_payload={"title": "Weekly planning", "summary": "", "tasks": []},
        next_step_name="summarize",
    )

    approval_blocked = orchestration.create_run(
        workflow_type="weekly_scheduling",
        first_step_name="dispatch_calendar_agent",
        request_payload=_request_payload(),
    )
    approval_blocked = orchestration.complete_current_step(
        approval_blocked.run.id,
        artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
        artifact_payload={
            "proposal_summary": "Hold deep work blocks and review windows this week.",
            "calendar_id": "primary",
            "time_blocks": [
                {
                    "title": "Deep work",
                    "start": "2026-03-16T09:00:00Z",
                    "end": "2026-03-16T11:00:00Z",
                }
            ],
            "proposed_changes": ["Reserve Monday and Tuesday mornings for deep work."],
        },
        next_step_name="apply_schedule",
    )

    failed = orchestration.create_run(
        workflow_type="weekly_digest",
        first_step_name="normalize_request",
        request_payload=_request_payload(),
    )
    orchestration.fail_current_step(
        failed.run.id,
        ExecutionFailurePayload(
            error_type="specialist_timeout",
            message="Task agent timed out.",
            retry_state=RetryState.RETRYABLE,
            retryable=True,
        ),
    )

    terminated = orchestration.create_run(
        workflow_type="weekly_digest",
        first_step_name="normalize_request",
        request_payload=_request_payload(),
    )
    failed_terminated = orchestration.fail_current_step(
        terminated.run.id,
        ExecutionFailurePayload(
            error_type="adapter_error",
            message="No adapter configured.",
            retry_state=RetryState.TERMINAL,
            retryable=False,
        ),
    )
    orchestration.terminate_run(failed_terminated.run.id, reason="Operator terminated failed run.")

    completed = orchestration.create_run(
        workflow_type="weekly_digest",
        first_step_name="normalize_request",
        request_payload=_request_payload(),
    )
    advanced = orchestration.complete_current_step(
        completed.run.id,
        artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
        artifact_payload=_normalized_payload(),
        next_step_name="summarize",
    )
    summary_payload = orchestration.build_final_summary_artifact(
        advanced.run.id,
        final_summary_text="Plan normalized and ready for review.",
    )
    artifact_repo.create(
        NewWorkflowArtifact(
            run_id=advanced.run.id,
            artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value,
            schema_version="2026-03-13",
            payload=summary_payload.model_dump(mode="json"),
        )
    )
    completed = orchestration.complete_current_step(
        advanced.run.id,
        artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value,
        artifact_payload=summary_payload.model_dump(mode="json"),
        next_step_name=None,
    )

    return {
        "running": running.run.id,
        "blocked": blocked.run.id,
        "approval_blocked": approval_blocked.run.id,
        "failed": failed.run.id,
        "terminated": terminated.run.id,
        "completed": completed.run.id,
    }


def _client() -> Generator[tuple[TestClient, Session], None, None]:
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


def test_create_workflow_route_defaults_to_weekly_scheduling_contract() -> None:
    for client, _session in _client():
        created = client.post(
            "/v1/workflow-runs",
            json={
                "request_text": (
                    "Plan my week. Tasks: Finish roadmap draft high due Wednesday 90m; "
                    "Prep interviews medium 120m. Constraints: protect deep work mornings; keep Friday afternoon open."
                ),
                "submitted_by": "telegram:user",
                "channel": "telegram",
                "metadata": {"chat_id": "999"},
            },
        )

        assert created.status_code == 200
        payload = created.json()
        assert payload["workflow_type"] == "weekly_scheduling"
        assert payload["current_step"] == "dispatch_task_agent"
        assert payload["weekly_request"]["tasks"][1]["title"] == "Prep interviews"
        assert payload["weekly_request"]["no_meeting_windows"] == ["keep Friday afternoon open."]


def test_workflow_routes_cover_operator_states() -> None:
    for client, session in _client():
        empty = client.get("/v1/workflow-runs")
        assert empty.status_code == 200
        assert empty.json() == []

        seeded = _seed_states(session)

        created = client.post(
            "/v1/workflow-runs",
            json={
                "request_text": (
                    "Plan my week. Tasks: Finish roadmap draft high due Wednesday 90m; "
                    "Prep interviews medium 120m. Constraints: protect deep work mornings; keep Friday afternoon open."
                ),
                "submitted_by": "telegram:user",
                "channel": "telegram",
                "metadata": {"chat_id": "999"},
            },
        )
        assert created.status_code == 200
        assert created.json()["status"] == WorkflowRunStatus.PENDING.value
        assert created.json()["workflow_type"] == "weekly_scheduling"
        assert created.json()["current_step"] == "dispatch_task_agent"
        assert created.json()["weekly_request"]["tasks"][0]["title"] == "Finish roadmap draft"
        assert created.json()["weekly_request"]["protected_time"] == ["protect deep work mornings"]

        non_empty = client.get("/v1/workflow-runs?limit=1")
        assert non_empty.status_code == 200
        assert len(non_empty.json()) == 1

        needs_action = client.get("/v1/workflow-runs?needs_action=true")
        assert needs_action.status_code == 200
        statuses = {item["status"] for item in needs_action.json()}
        assert WorkflowRunStatus.BLOCKED.value in statuses
        assert WorkflowRunStatus.FAILED.value in statuses

        running = client.get(f"/v1/workflow-runs/{seeded['running']}")
        assert running.status_code == 200
        assert running.json()["status"] == WorkflowRunStatus.RUNNING.value
        assert running.json()["lineage"]["validation_artifacts"][0]["payload"]["outcome"] == "passed"

        blocked = client.get(f"/v1/workflow-runs/{seeded['blocked']}")
        assert blocked.status_code == 200
        assert blocked.json()["paused_state"] == "blocked_validation"
        assert blocked.json()["lineage"]["events"][-1]["event_type"] == "validation_failed"

        approval_blocked = client.get(f"/v1/workflow-runs/{seeded['approval_blocked']}")
        assert approval_blocked.status_code == 200
        assert approval_blocked.json()["paused_state"] == "awaiting_approval"
        assert approval_blocked.json()["approval_checkpoint"]["allowed_actions"] == [
            "approve",
            "reject",
            "request_revision",
        ]
        target_artifact_id = approval_blocked.json()["approval_checkpoint"]["target_artifact_id"]
        assert approval_blocked.json()["approval_checkpoint"]["target_version_number"] == 1

        proposal_versions = client.get(f"/v1/workflow-runs/{seeded['approval_blocked']}/proposal-versions")
        assert proposal_versions.status_code == 200
        assert proposal_versions.json()[0]["artifact_id"] == target_artifact_id

        approve = client.post(
            f"/v1/workflow-runs/{seeded['approval_blocked']}/approve",
            json={"actor": "api:test", "target_artifact_id": target_artifact_id},
        )
        assert approve.status_code == 200
        assert approve.json()["status"] == WorkflowRunStatus.PENDING.value
        assert approve.json()["current_step"] == "apply_schedule"

        retry = client.post(
            f"/v1/workflow-runs/{seeded['blocked']}/retry",
            json={"reason": "Operator requested retry after correction."},
        )
        assert retry.status_code == 200
        assert retry.json()["status"] == WorkflowRunStatus.PENDING.value

        failed = client.get(f"/v1/workflow-runs/{seeded['failed']}")
        assert failed.status_code == 200
        assert failed.json()["failure_kind"] == "execution_failed"
        assert failed.json()["lineage"]["validation_artifacts"] == []

        rejection_seed = _seed_states(session)["approval_blocked"]
        rejection_detail = client.get(f"/v1/workflow-runs/{rejection_seed}")
        rejection_target = rejection_detail.json()["approval_checkpoint"]["target_artifact_id"]
        reject = client.post(
            f"/v1/workflow-runs/{rejection_seed}/reject",
            json={"actor": "api:test", "target_artifact_id": rejection_target},
        )
        assert reject.status_code == 200
        assert reject.json()["status"] == WorkflowRunStatus.TERMINATED.value

        revision_seed = _seed_states(session)["approval_blocked"]
        revision_detail = client.get(f"/v1/workflow-runs/{revision_seed}")
        revision_target = revision_detail.json()["approval_checkpoint"]["target_artifact_id"]
        revision = client.post(
            f"/v1/workflow-runs/{revision_seed}/request-revision",
            json={
                "actor": "api:test",
                "target_artifact_id": revision_target,
                "feedback": "Keep Friday afternoon open.",
            },
        )
        assert revision.status_code == 200
        assert revision.json()["status"] == WorkflowRunStatus.PENDING.value
        assert revision.json()["current_step"] == "dispatch_calendar_agent"
        assert revision.json()["latest_decision"]["revision_feedback"] == "Keep Friday afternoon open."

        terminate = client.post(
            f"/v1/workflow-runs/{seeded['failed']}/terminate",
            json={"reason": "Operator terminated failed run."},
        )
        assert terminate.status_code == 200
        assert terminate.json()["status"] == WorkflowRunStatus.TERMINATED.value

        terminated = client.get(f"/v1/workflow-runs/{seeded['terminated']}")
        assert terminated.status_code == 200
        assert terminated.json()["status"] == WorkflowRunStatus.TERMINATED.value

        completed = client.get(f"/v1/workflow-runs/{seeded['completed']}")
        assert completed.status_code == 200
        assert completed.json()["status"] == WorkflowRunStatus.COMPLETED.value
        assert completed.json()["lineage"]["final_summary"]["approval_decision_artifact_id"] is None
        assert completed.json()["lineage"]["final_summary"]["downstream_sync_reference_ids"] == []
