from datetime import UTC, datetime

from helm_api.services.workflow_status_service import WorkflowRunCreateInput, WorkflowStatusService
from helm_orchestration import (
    ScheduleProposalValidator,
    ValidationOutcome,
    ExecutionFailurePayload,
    NormalizedTaskValidator,
    RegisteredValidator,
    RetryState,
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
    WorkflowStepStatus,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _create_input() -> WorkflowRunCreateInput:
    return WorkflowRunCreateInput(
        workflow_type="weekly_digest",
        first_step_name="normalize_request",
        request_text="Plan my week around deep work.",
        submitted_by="telegram:user",
        channel="telegram",
        metadata={"chat_id": "123"},
    )


def _orchestration(session: Session) -> WorkflowOrchestrationService:
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


def _create_approval_blocked_run(session: Session) -> int:
    orchestration = _orchestration(session)
    created = orchestration.create_run(
        workflow_type="weekly_scheduling",
        first_step_name="dispatch_calendar_agent",
        request_payload={
            "request_text": "Plan my week around deep work.",
            "submitted_by": "telegram:user",
            "channel": "telegram",
            "metadata": {"chat_id": "123"},
        },
    )
    blocked = orchestration.complete_current_step(
        created.run.id,
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
    assert blocked.run.status == WorkflowRunStatus.BLOCKED.value
    return blocked.run.id


def test_create_run_summary_answers_operator_triage_question() -> None:
    with _session() as session:
        service = WorkflowStatusService(session)

        created = service.create_run(_create_input())

        assert created["workflow_type"] == "weekly_digest"
        assert created["status"] == WorkflowRunStatus.PENDING.value
        assert created["current_step"] == "normalize_request"
        assert created["paused_state"] is None
        assert created["needs_action"] is False
        assert created["last_event_summary"] == "Workflow run created"
        assert created["available_actions"] == []


def test_blocked_run_summary_distinguishes_validation_failure() -> None:
    with _session() as session:
        orchestration = _orchestration(session)
        created = orchestration.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload={
                "request_text": "Plan my week around deep work.",
                "submitted_by": "telegram:user",
                "channel": "telegram",
                "metadata": {"chat_id": "123"},
            },
        )
        orchestration.complete_current_step(
            created.run.id,
            artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
            artifact_payload={"title": "Weekly planning", "summary": "", "tasks": []},
            next_step_name="summarize",
        )

        summary = WorkflowStatusService(session).list_runs(needs_action=True)[0]

        assert summary["status"] == WorkflowRunStatus.BLOCKED.value
        assert summary["paused_state"] == "blocked_validation"
        assert summary["failure_kind"] == "blocked_validation"
        assert summary["failure_summary"] == "Normalized task artifact failed validation."
        assert summary["retryable"] is True
        assert [action["action"] for action in summary["available_actions"]] == ["retry", "terminate"]


def test_approval_blocked_run_summary_projects_checkpoint_state() -> None:
    with _session() as session:
        run_id = _create_approval_blocked_run(session)

        summary = WorkflowStatusService(session).get_run_detail(run_id)

        assert summary is not None
        assert summary["status"] == WorkflowRunStatus.BLOCKED.value
        assert summary["paused_state"] == "awaiting_approval"
        assert summary["failure_kind"] == "approval_required"
        assert summary["approval_checkpoint"]["proposal_summary"] == (
            "Hold deep work blocks and review windows this week."
        )
        assert summary["approval_checkpoint"]["allowed_actions"] == [
            "approve",
            "reject",
            "request_revision",
        ]
        assert [action["action"] for action in summary["available_actions"]] == [
            "approve",
            "reject",
            "request_revision",
        ]
        assert summary["latest_validation_outcome"] == ValidationOutcome.PASSED.value
        assert summary["latest_decision"] is None


def test_failed_run_detail_exposes_lineage_without_validation_artifact() -> None:
    with _session() as session:
        orchestration = WorkflowOrchestrationService(session)
        created = orchestration.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload={
                "request_text": "Plan my week around deep work.",
                "submitted_by": "telegram:user",
                "channel": "telegram",
                "metadata": {"chat_id": "123"},
            },
        )
        failed = orchestration.fail_current_step(
            created.run.id,
            ExecutionFailurePayload(
                error_type="specialist_timeout",
                message="Task agent timed out.",
                retry_state=RetryState.RETRYABLE,
                retryable=True,
                details={"provider": "task-agent"},
            ),
        )

        detail = WorkflowStatusService(session).get_run_detail(failed.run.id)

        assert detail is not None
        assert detail["status"] == WorkflowRunStatus.FAILED.value
        assert detail["paused_state"] == "awaiting_retry"
        assert detail["failure_kind"] == "execution_failed"
        assert detail["lineage"]["raw_request"]["artifact_type"] == WorkflowArtifactType.RAW_REQUEST.value
        assert detail["lineage"]["validation_artifacts"] == []
        assert detail["lineage"]["final_summary"]["approval_decision_artifact_id"] is None
        assert detail["lineage"]["final_summary"]["downstream_sync_reference_ids"] == []
        assert detail["lineage"]["step_transitions"][0]["status"] == WorkflowStepStatus.FAILED.value
        assert detail["lineage"]["events"][-1]["event_type"] == "execution_failed"


def test_completed_run_detail_exposes_final_summary_contract() -> None:
    with _session() as session:
        orchestration = _orchestration(session)
        created = orchestration.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload={
                "request_text": "Plan my week around deep work.",
                "submitted_by": "telegram:user",
                "channel": "telegram",
                "metadata": {"chat_id": "123"},
            },
        )
        advanced = orchestration.complete_current_step(
            created.run.id,
            artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
            artifact_payload={
                "title": "Weekly planning",
                "summary": "Focus on deep work blocks.",
                "tasks": [{"title": "Deep work", "summary": "Plan", "priority": "high", "estimated_minutes": 90}],
            },
            next_step_name="summarize",
        )
        summary_payload = orchestration.build_final_summary_artifact(
            advanced.run.id,
            final_summary_text="Plan normalized and ready for review.",
        )
        SQLAlchemyWorkflowArtifactRepository(session).create(
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

        detail = WorkflowStatusService(session).get_run_detail(completed.run.id)

        assert detail is not None
        assert detail["status"] == WorkflowRunStatus.COMPLETED.value
        assert detail["lineage"]["final_summary"]["request_artifact_id"] is not None
        assert detail["lineage"]["final_summary"]["approval_decision"] is None
        assert detail["lineage"]["final_summary"]["downstream_sync_status"] is None
        assert detail["lineage"]["final_summary"]["downstream_sync_artifact_ids"] == []
