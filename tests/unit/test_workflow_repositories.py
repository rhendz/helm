from datetime import UTC, datetime

from helm_storage.db import Base
from helm_storage.repositories import (
    NormalizedTaskArtifactPayload,
    RawRequestArtifactPayload,
    SQLAlchemyWorkflowArtifactRepository,
    SQLAlchemyWorkflowEventRepository,
    SQLAlchemyWorkflowRunRepository,
    SQLAlchemyWorkflowStepRepository,
    ValidationArtifactPayload,
    WorkflowArtifactRepository,
    WorkflowArtifactType,
    WorkflowEventRepository,
    WorkflowRunPatch,
    WorkflowRunRepository,
    WorkflowRunStatus,
    WorkflowStepPatch,
    WorkflowStepRepository,
    WorkflowStepStatus,
    WorkflowSummaryArtifactPayload,
)
from helm_storage.repositories.contracts import (
    NewWorkflowArtifact,
    NewWorkflowEvent,
    NewWorkflowRun,
    NewWorkflowStep,
)
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_workflow_schema_tables_exist_in_metadata() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)

    assert set(inspector.get_table_names()) >= {
        "workflow_runs",
        "workflow_steps",
        "workflow_artifacts",
        "workflow_events",
    }

    run_columns = {column["name"] for column in inspector.get_columns("workflow_runs")}
    assert {"status", "current_step_name", "needs_action", "validation_outcome_summary"} <= run_columns

    step_columns = {column["name"] for column in inspector.get_columns("workflow_steps")}
    assert {"step_name", "attempt_number", "failure_class", "retry_state"} <= step_columns

    artifact_columns = {column["name"] for column in inspector.get_columns("workflow_artifacts")}
    assert {
        "artifact_type",
        "schema_version",
        "version_number",
        "lineage_parent_id",
        "supersedes_artifact_id",
        "payload",
    } <= artifact_columns

    event_columns = {column["name"] for column in inspector.get_columns("workflow_events")}
    assert {"event_type", "run_status", "step_status", "details"} <= event_columns


def test_workflow_repositories_persist_raw_request_and_resume_safe_state() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        event_repo = SQLAlchemyWorkflowEventRepository(session)

        assert isinstance(run_repo, WorkflowRunRepository)
        assert isinstance(step_repo, WorkflowStepRepository)
        assert isinstance(artifact_repo, WorkflowArtifactRepository)
        assert isinstance(event_repo, WorkflowEventRepository)

        run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_digest",
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name="normalize_request",
                current_step_attempt=1,
                attempt_count=1,
            )
        )
        step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="normalize_request",
                status=WorkflowStepStatus.RUNNING.value,
                attempt_number=1,
            )
        )
        raw_request = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=step.id,
                artifact_type=WorkflowArtifactType.RAW_REQUEST.value,
                schema_version="2026-03-13",
                producer_step_name=step.step_name,
                payload=RawRequestArtifactPayload(
                    request_text="Prepare the weekly digest",
                    submitted_by="telegram:user",
                    channel="telegram",
                    metadata={"chat_id": "123"},
                ).to_dict(),
            )
        )
        event_repo.create(
            NewWorkflowEvent(
                run_id=run.id,
                step_id=step.id,
                event_type="step_started",
                run_status=WorkflowRunStatus.RUNNING.value,
                step_status=WorkflowStepStatus.RUNNING.value,
                summary="Normalization started",
                details={"step_name": step.step_name},
            )
        )

        current_state = run_repo.get_with_current_state(run.id)
        assert current_state is not None
        assert current_state.run.id == run.id
        assert current_state.current_step is not None
        assert current_state.current_step.id == step.id
        assert current_state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value].id == raw_request.id
        assert current_state.last_event is not None
        assert current_state.last_event.summary == "Normalization started"


def test_workflow_artifact_versioning_validation_and_summary_lineage() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)

        run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_digest",
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name="summarize",
                current_step_attempt=1,
                attempt_count=3,
            )
        )
        normalize_step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="normalize_request",
                status=WorkflowStepStatus.SUCCEEDED.value,
                attempt_number=1,
                completed_at=datetime.now(UTC),
            )
        )
        validate_step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="validate_normalized_task",
                status=WorkflowStepStatus.SUCCEEDED.value,
                attempt_number=1,
                validation_outcome_summary="passed_with_warnings",
                completed_at=datetime.now(UTC),
            )
        )
        summarize_step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="summarize",
                status=WorkflowStepStatus.SUCCEEDED.value,
                attempt_number=1,
                completed_at=datetime.now(UTC),
            )
        )

        request_artifact = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=normalize_step.id,
                artifact_type=WorkflowArtifactType.RAW_REQUEST.value,
                schema_version="2026-03-13",
                producer_step_name=normalize_step.step_name,
                payload=RawRequestArtifactPayload(
                    request_text="Build a digest from this backlog",
                    submitted_by="telegram:user",
                    channel="telegram",
                    metadata={"chat_id": "123"},
                ).to_dict(),
            )
        )
        normalized_v1 = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=normalize_step.id,
                artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
                schema_version="2026-03-13",
                producer_step_name=normalize_step.step_name,
                lineage_parent_id=request_artifact.id,
                payload=NormalizedTaskArtifactPayload(
                    title="Digest backlog",
                    summary="First pass",
                    tasks=("triage inbox",),
                ).to_dict(),
            )
        )
        normalized_v2 = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=normalize_step.id,
                artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
                schema_version="2026-03-13",
                producer_step_name=normalize_step.step_name,
                lineage_parent_id=request_artifact.id,
                supersedes_artifact_id=normalized_v1.id,
                payload=NormalizedTaskArtifactPayload(
                    title="Digest backlog",
                    summary="Second pass",
                    tasks=("triage inbox", "draft priorities"),
                    warnings=("Needs human review of project priority ordering",),
                ).to_dict(),
            )
        )
        validation_artifact = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=validate_step.id,
                artifact_type=WorkflowArtifactType.VALIDATION_RESULT.value,
                schema_version="2026-03-13",
                producer_step_name=validate_step.step_name,
                lineage_parent_id=normalized_v2.id,
                payload=ValidationArtifactPayload(
                    outcome="passed_with_warnings",
                    summary="Task payload is valid with a priority warning",
                    validator_name="normalized-task-validator",
                    schema_version="2026-03-13",
                    warnings=("Priority ordering may need manual review",),
                ).to_dict(),
            )
        )
        summary_artifact = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=summarize_step.id,
                artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value,
                schema_version="2026-03-13",
                producer_step_name=summarize_step.step_name,
                lineage_parent_id=validation_artifact.id,
                payload=WorkflowSummaryArtifactPayload(
                    request_artifact_id=request_artifact.id,
                    intermediate_artifact_ids=(normalized_v2.id,),
                    validation_artifact_ids=(validation_artifact.id,),
                    final_summary_text="Digest ready for operator review",
                    approval_decision=None,
                    approval_decision_artifact_id=None,
                    downstream_sync_status=None,
                    downstream_sync_artifact_ids=(),
                    downstream_sync_reference_ids=(),
                ).to_dict(),
            )
        )

        latest_by_type = artifact_repo.get_latest_by_type(run.id)
        assert latest_by_type[WorkflowArtifactType.NORMALIZED_TASK.value].id == normalized_v2.id
        assert latest_by_type[WorkflowArtifactType.FINAL_SUMMARY.value].id == summary_artifact.id

        summary_payload = latest_by_type[WorkflowArtifactType.FINAL_SUMMARY.value].payload
        assert summary_payload["request_artifact_id"] == request_artifact.id
        assert summary_payload["intermediate_artifact_ids"] == [normalized_v2.id]
        assert summary_payload["validation_artifact_ids"] == [validation_artifact.id]
        assert summary_payload["approval_decision"] is None
        assert summary_payload["approval_decision_artifact_id"] is None
        assert summary_payload["downstream_sync_status"] is None
        assert summary_payload["downstream_sync_artifact_ids"] == []
        assert summary_payload["downstream_sync_reference_ids"] == []


def test_workflow_failure_and_blocked_validation_states_stay_distinct() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)

        failed_run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_digest",
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name="execute_specialist",
                current_step_attempt=1,
                attempt_count=1,
            )
        )
        failed_step = step_repo.create(
            NewWorkflowStep(
                run_id=failed_run.id,
                step_name="execute_specialist",
                status=WorkflowStepStatus.RUNNING.value,
                attempt_number=1,
            )
        )
        step_repo.update(
            failed_step.id,
            WorkflowStepPatch(
                status=WorkflowStepStatus.FAILED.value,
                execution_error_summary="Specialist timed out while generating tasks",
                failure_class="timeout",
                retry_state="retryable",
                retryable=True,
                completed_at=datetime.now(UTC),
            ),
        )
        run_repo.update(
            failed_run.id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.FAILED.value,
                execution_error_summary="Specialist timed out while generating tasks",
                failure_class="timeout",
                retry_state="retryable",
                last_event_summary="Execution failed in specialist step",
            ),
        )

        blocked_run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_digest",
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name="validate_normalized_task",
                current_step_attempt=1,
                attempt_count=2,
            )
        )
        blocked_step = step_repo.create(
            NewWorkflowStep(
                run_id=blocked_run.id,
                step_name="validate_normalized_task",
                status=WorkflowStepStatus.RUNNING.value,
                attempt_number=1,
            )
        )
        step_repo.update(
            blocked_step.id,
            WorkflowStepPatch(
                status=WorkflowStepStatus.VALIDATION_FAILED.value,
                validation_outcome_summary="Validation failed: missing title",
                failure_class="schema_validation_failed",
                retry_state="awaiting_operator",
                retryable=False,
                completed_at=datetime.now(UTC),
            ),
        )
        run_repo.update(
            blocked_run.id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.BLOCKED.value,
                needs_action=True,
                validation_outcome_summary="Validation failed: missing title",
                failure_class="schema_validation_failed",
                retry_state="awaiting_operator",
                last_event_summary="Validation blocked run progression",
            ),
        )

        last_failed_step = step_repo.get_last_failed_for_run(failed_run.id)
        assert last_failed_step is not None
        assert last_failed_step.status == WorkflowStepStatus.FAILED.value
        assert last_failed_step.execution_error_summary == "Specialist timed out while generating tasks"
        assert last_failed_step.retryable is True
        assert last_failed_step.retry_state == "retryable"

        last_blocked_step = step_repo.get_last_failed_for_run(blocked_run.id)
        assert last_blocked_step is not None
        assert last_blocked_step.status == WorkflowStepStatus.VALIDATION_FAILED.value
        assert last_blocked_step.validation_outcome_summary == "Validation failed: missing title"
        assert last_blocked_step.retryable is False
        assert last_blocked_step.retry_state == "awaiting_operator"

        needing_action = run_repo.list_needing_action()
        assert [state.run.id for state in needing_action] == [blocked_run.id]


def test_workflow_run_queries_reconstruct_runnable_state_after_interruption() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        event_repo = SQLAlchemyWorkflowEventRepository(session)

        runnable_run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_digest",
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name="summarize",
                current_step_attempt=2,
                attempt_count=4,
            )
        )
        first_attempt = step_repo.create(
            NewWorkflowStep(
                run_id=runnable_run.id,
                step_name="summarize",
                status=WorkflowStepStatus.FAILED.value,
                attempt_number=1,
                execution_error_summary="Transient LLM error",
                failure_class="transient_model_error",
                retry_state="retryable",
                retryable=True,
                completed_at=datetime.now(UTC),
            )
        )
        second_attempt = step_repo.create(
            NewWorkflowStep(
                run_id=runnable_run.id,
                step_name="summarize",
                status=WorkflowStepStatus.RUNNING.value,
                attempt_number=2,
            )
        )
        artifact_repo.create(
            NewWorkflowArtifact(
                run_id=runnable_run.id,
                step_id=first_attempt.id,
                artifact_type=WorkflowArtifactType.NORMALIZED_TASK.value,
                schema_version="2026-03-13",
                producer_step_name="normalize_request",
                payload=NormalizedTaskArtifactPayload(
                    title="Digest backlog",
                    summary="Recovered after interruption",
                    tasks=("triage inbox", "send follow-up"),
                ).to_dict(),
            )
        )
        event_repo.create(
            NewWorkflowEvent(
                run_id=runnable_run.id,
                step_id=second_attempt.id,
                event_type="run_resumed",
                run_status=WorkflowRunStatus.RUNNING.value,
                step_status=WorkflowStepStatus.RUNNING.value,
                summary="Run resumed on summarize attempt 2",
                details={"attempt_number": 2},
            )
        )

        blocked_run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_digest",
                status=WorkflowRunStatus.BLOCKED.value,
                current_step_name="validate_normalized_task",
                current_step_attempt=1,
                attempt_count=2,
                needs_action=True,
                validation_outcome_summary="Awaiting operator decision",
            )
        )
        step_repo.create(
            NewWorkflowStep(
                run_id=blocked_run.id,
                step_name="validate_normalized_task",
                status=WorkflowStepStatus.VALIDATION_FAILED.value,
                attempt_number=1,
                validation_outcome_summary="Awaiting operator decision",
                completed_at=datetime.now(UTC),
            )
        )

        runnable = run_repo.list_runnable()
        assert [state.run.id for state in runnable] == [runnable_run.id]
        assert runnable[0].current_step is not None
        assert runnable[0].current_step.id == second_attempt.id
        assert runnable[0].latest_artifacts[WorkflowArtifactType.NORMALIZED_TASK.value].payload["summary"] == (
            "Recovered after interruption"
        )
        assert runnable[0].last_event is not None
        assert runnable[0].last_event.summary == "Run resumed on summarize attempt 2"

        needing_action = run_repo.list_needing_action()
        assert [state.run.id for state in needing_action] == [blocked_run.id]
