from helm_orchestration import (
    ExecutionFailurePayload,
    NormalizedTaskArtifact,
    NormalizedTaskValidator,
    RegisteredValidator,
    RetryState,
    StepExecutionResult,
    TaskArtifact,
    ValidationOutcome,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowArtifactKind,
    WorkflowOrchestrationService,
    WorkflowResumeService,
    WorkflowSummaryArtifact,
    WorkflowStepExecutionError,
)
from helm_storage.db import Base
from helm_storage.repositories import WorkflowArtifactType, WorkflowRunStatus, WorkflowStepStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_validation_registry_uses_step_name_targets() -> None:
    registry = ValidatorRegistry(
        [
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.STEP_NAME,
                    value="validate_normalized_task",
                ),
                validator=NormalizedTaskValidator(),
            )
        ]
    )

    report = registry.validate_for_step(
        "validate_normalized_task",
        NormalizedTaskArtifact(
            title="Weekly planning",
            summary="Turn backlog items into a weekly plan.",
            tasks=(
                TaskArtifact(
                    title="Triage inbox",
                    summary="Clear pending email.",
                    priority="high",
                    estimated_minutes=30,
                ),
            ),
        ),
    )

    assert report.outcome is ValidationOutcome.PASSED


def test_validation_registry_reports_warnings_by_artifact_type() -> None:
    registry = ValidatorRegistry(
        [
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.ARTIFACT_TYPE,
                    value=WorkflowArtifactKind.NORMALIZED_TASK.value,
                ),
                validator=NormalizedTaskValidator(),
            )
        ]
    )

    report = registry.validate_for_artifact_type(
        WorkflowArtifactKind.NORMALIZED_TASK.value,
        {
            "title": "Weekly planning",
            "summary": "Turn backlog items into a weekly plan.",
            "tasks": [
                {
                    "title": "Triage inbox",
                    "summary": "Clear pending email.",
                    "estimated_minutes": 30,
                }
            ],
        },
    )

    assert report.outcome is ValidationOutcome.PASSED_WITH_WARNINGS
    assert report.warnings == ("Task 1 is missing a priority.",)


def test_validation_registry_blocks_incomplete_artifacts() -> None:
    validator = NormalizedTaskValidator()

    report = validator.validate(
        {
            "title": "Weekly planning",
            "summary": "",
            "tasks": [],
        }
    )

    assert report.outcome is ValidationOutcome.FAILED
    assert {issue.code for issue in report.issues} == {"missing_summary", "missing_tasks"}


def test_workflow_summary_schema_keeps_phase_one_optional_linkage_fields() -> None:
    summary = WorkflowSummaryArtifact(
        request_artifact_id=1,
        intermediate_artifact_ids=(2,),
        validation_artifact_ids=(3,),
        final_summary_text="Normalized plan is ready for operator review.",
    )

    payload = summary.model_dump(mode="json")

    assert payload["approval_decision"] is None
    assert payload["approval_decision_artifact_id"] is None
    assert payload["downstream_sync_status"] is None
    assert payload["downstream_sync_artifact_ids"] == []
    assert payload["downstream_sync_reference_ids"] == []


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _request_payload() -> dict[str, object]:
    return {
        "request_text": "Plan my week.",
        "submitted_by": "telegram:user",
        "channel": "telegram",
        "metadata": {"chat_id": "123"},
    }


def _normalized_task(*, priority: str | None = "high") -> NormalizedTaskArtifact:
    return NormalizedTaskArtifact(
        title="Weekly planning",
        summary="Turn backlog items into a weekly plan.",
        tasks=(
            TaskArtifact(
                title="Triage inbox",
                summary="Clear pending email.",
                priority=priority,
                estimated_minutes=30,
            ),
        ),
    )


def _service(session: Session) -> WorkflowOrchestrationService:
    registry = ValidatorRegistry(
        [
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.STEP_NAME,
                    value="normalize_request",
                ),
                validator=NormalizedTaskValidator(),
            )
        ]
    )
    return WorkflowOrchestrationService(session, validator_registry=registry)


def test_validation_failure_blocks_run_durably() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )

        state = service.complete_current_step(
            created.run.id,
            artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
            artifact_payload={
                "title": "Weekly planning",
                "summary": "",
                "tasks": [],
            },
            next_step_name="summarize",
        )

        assert state.run.status == WorkflowRunStatus.BLOCKED.value
        assert state.run.needs_action is True
        assert state.run.retry_state == RetryState.AWAITING_OPERATOR.value
        assert state.current_step is not None
        assert state.current_step.status == WorkflowStepStatus.VALIDATION_FAILED.value
        assert state.latest_artifacts[WorkflowArtifactType.VALIDATION_RESULT.value].payload["outcome"] == (
            ValidationOutcome.FAILED.value
        )


def test_successful_step_persists_validation_and_advances_to_next_step() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )

        state = service.complete_current_step(
            created.run.id,
            artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
            artifact_payload=_normalized_task(priority=None),
            next_step_name="summarize",
        )

        assert state.run.status == WorkflowRunStatus.RUNNING.value
        assert state.run.current_step_name == "summarize"
        assert state.current_step is not None
        assert state.current_step.step_name == "summarize"
        assert state.current_step.status == WorkflowStepStatus.PENDING.value
        assert state.latest_artifacts[WorkflowArtifactType.VALIDATION_RESULT.value].payload["outcome"] == (
            ValidationOutcome.PASSED_WITH_WARNINGS.value
        )


def test_execution_failure_persists_failed_step_and_retryability() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )

        state = service.fail_current_step(
            created.run.id,
            ExecutionFailurePayload(
                error_type="specialist_timeout",
                message="Task agent timed out.",
                retry_state=RetryState.RETRYABLE,
                retryable=True,
                details={"step_name": "normalize_request"},
            ),
        )

        assert state.run.status == WorkflowRunStatus.FAILED.value
        assert state.run.needs_action is True
        assert state.run.execution_error_summary == "Task agent timed out."
        assert state.current_step is not None
        assert state.current_step.status == WorkflowStepStatus.FAILED.value
        assert state.current_step.retryable is True


def test_retry_requeues_last_failed_step_without_advancing() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )
        service.complete_current_step(
            created.run.id,
            artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
            artifact_payload={
                "title": "Weekly planning",
                "summary": "",
                "tasks": [],
            },
            next_step_name="summarize",
        )

        state = service.retry_current_step(created.run.id, reason="Operator requested retry after correction.")

        assert state.run.status == WorkflowRunStatus.PENDING.value
        assert state.run.current_step_name == "normalize_request"
        assert state.run.current_step_attempt == 2
        assert state.current_step is not None
        assert state.current_step.step_name == "normalize_request"
        assert state.current_step.attempt_number == 2
        assert state.current_step.status == WorkflowStepStatus.PENDING.value


def test_terminate_marks_run_terminal_without_downstream_advance() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )
        failed = service.fail_current_step(
            created.run.id,
            ExecutionFailurePayload(
                error_type="adapter_free_execution_error",
                message="No specialist available.",
                retry_state=RetryState.TERMINAL,
                retryable=False,
            ),
        )

        state = service.terminate_run(failed.run.id, reason="Operator terminated failed run.")

        assert state.run.status == WorkflowRunStatus.TERMINATED.value
        assert state.run.needs_action is False
        assert state.run.retry_state == RetryState.TERMINAL.value


def test_resume_service_uses_persisted_state_after_interruption() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            handlers={
                "normalize_request": lambda _state: StepExecutionResult(
                    artifact_type=WorkflowArtifactKind.NORMALIZED_TASK,
                    payload=_normalized_task(priority="high"),
                    next_step_name="summarize",
                )
            },
        )

        resumed = resume_service.resume_run(created.run.id)

        assert resumed.run.current_step_name == "summarize"
        assert resumed.run.status == WorkflowRunStatus.RUNNING.value
        assert resumed.latest_artifacts[WorkflowArtifactType.NORMALIZED_TASK.value].payload["title"] == (
            "Weekly planning"
        )


def test_resume_service_skips_blocked_runs_until_explicit_retry() -> None:
    with _session() as session:
        service = _service(session)
        blocked = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )
        runnable = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )
        service.complete_current_step(
            blocked.run.id,
            artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
            artifact_payload={"title": "Weekly planning", "summary": "", "tasks": []},
            next_step_name="summarize",
        )
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            handlers={
                "normalize_request": lambda _state: StepExecutionResult(
                    artifact_type=WorkflowArtifactKind.NORMALIZED_TASK,
                    payload=_normalized_task(),
                    next_step_name="summarize",
                )
            },
        )

        initial_runnable = resume_service.list_runnable_runs()
        assert [state.run.id for state in initial_runnable] == [runnable.run.id]

        service.retry_current_step(blocked.run.id, reason="Operator requested retry.")
        retried_runnable = resume_service.list_runnable_runs()
        assert [state.run.id for state in retried_runnable] == [blocked.run.id, runnable.run.id]


def test_resume_service_records_handler_exceptions_as_failed_runs() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            handlers={
                "normalize_request": lambda _state: (_ for _ in ()).throw(
                    WorkflowStepExecutionError(
                        ExecutionFailurePayload(
                            error_type="specialist_timeout",
                            message="Task agent timed out.",
                            retry_state=RetryState.RETRYABLE,
                            retryable=True,
                        )
                    )
                )
            },
        )

        failed = resume_service.resume_run(created.run.id)

        assert failed.run.status == WorkflowRunStatus.FAILED.value
        assert failed.current_step is not None
        assert failed.current_step.status == WorkflowStepStatus.FAILED.value


def test_final_summary_artifact_creation_completes_workflow() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_digest",
            first_step_name="normalize_request",
            request_payload=_request_payload(),
        )
        advanced = service.complete_current_step(
            created.run.id,
            artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
            artifact_payload=_normalized_task(),
            next_step_name="summarize",
        )
        summary_payload = service.build_final_summary_artifact(
            advanced.run.id,
            final_summary_text="Workflow ready for operator review.",
        )

        state = service.complete_current_step(
            advanced.run.id,
            artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value,
            artifact_payload=summary_payload,
        )

        assert state.run.status == WorkflowRunStatus.COMPLETED.value
        assert state.latest_artifacts[WorkflowArtifactType.FINAL_SUMMARY.value].payload["final_summary_text"] == (
            "Workflow ready for operator review."
        )
