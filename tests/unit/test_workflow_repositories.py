from datetime import UTC, datetime

from helm_storage.db import Base
from helm_storage.repositories import (
    ApprovalDecisionArtifactPayload,
    ApprovalRequestArtifactPayload,
    NewWorkflowSyncRecord,
    NormalizedTaskArtifactPayload,
    NewWorkflowApprovalCheckpoint,
    RawRequestArtifactPayload,
    ScheduleProposalArtifactPayload,
    SQLAlchemyWorkflowApprovalCheckpointRepository,
    SQLAlchemyWorkflowArtifactRepository,
    SQLAlchemyWorkflowEventRepository,
    SQLAlchemyWorkflowRunRepository,
    SQLAlchemyWorkflowSpecialistInvocationRepository,
    SQLAlchemyWorkflowSyncRecordRepository,
    SQLAlchemyWorkflowStepRepository,
    ValidationArtifactPayload,
    WorkflowArtifactRepository,
    WorkflowArtifactType,
    WorkflowApprovalCheckpointPatch,
    WorkflowApprovalCheckpointRepository,
    WorkflowBlockedReason,
    WorkflowEventRepository,
    WorkflowRunPatch,
    WorkflowRunRepository,
    WorkflowRunStatus,
    WorkflowSpecialistInvocationRepository,
    WorkflowSpecialistInvocationPatch,
    WorkflowSyncFailedQuery,
    WorkflowSyncKind,
    WorkflowSyncRecordPatch,
    WorkflowSyncRecordRepository,
    WorkflowSyncRemainingQuery,
    WorkflowSyncStatus,
    WorkflowSyncStepQuery,
    WorkflowTargetSystem,
    WorkflowStepPatch,
    WorkflowStepRepository,
    WorkflowStepStatus,
    WorkflowSummaryArtifactPayload,
)
from helm_storage.repositories.contracts import (
    NewWorkflowArtifact,
    NewWorkflowEvent,
    NewWorkflowRun,
    NewWorkflowSpecialistInvocation,
    NewWorkflowStep,
)
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_workflow_schema_tables_include_specialist_dispatch_metadata() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)

    assert set(inspector.get_table_names()) >= {
        "workflow_runs",
        "workflow_steps",
        "workflow_artifacts",
        "workflow_events",
        "workflow_approval_checkpoints",
        "workflow_specialist_invocations",
        "workflow_sync_records",
    }

    run_columns = {column["name"] for column in inspector.get_columns("workflow_runs")}
    assert {
        "status",
        "current_step_name",
        "needs_action",
        "validation_outcome_summary",
        "blocked_reason",
        "resume_step_name",
        "resume_step_attempt",
    } <= run_columns

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

    approval_columns = {
        column["name"] for column in inspector.get_columns("workflow_approval_checkpoints")
    }
    assert {
        "run_id",
        "step_id",
        "target_artifact_id",
        "resume_step_name",
        "resume_step_attempt",
        "allowed_actions",
        "status",
        "decision",
        "decision_actor",
        "decision_at",
        "revision_feedback",
        "resolved_at",
    } <= approval_columns

    invocation_columns = {
        column["name"] for column in inspector.get_columns("workflow_specialist_invocations")
    }
    assert {
        "run_id",
        "step_id",
        "specialist_name",
        "input_artifact_id",
        "output_artifact_id",
        "status",
        "started_at",
        "completed_at",
        "error_summary",
    } <= invocation_columns

    sync_columns = {column["name"] for column in inspector.get_columns("workflow_sync_records")}
    assert {
        "proposal_artifact_id",
        "proposal_version_number",
        "target_system",
        "sync_kind",
        "planned_item_key",
        "execution_order",
        "status",
        "idempotency_key",
        "payload_fingerprint",
        "external_object_id",
        "last_error_summary",
        "attempt_count",
        "last_attempt_step_id",
        "last_attempted_at",
        "completed_at",
        "supersedes_sync_record_id",
        "replayed_from_sync_record_id",
    } <= sync_columns


def test_workflow_repositories_persist_raw_request_and_resume_safe_state() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        event_repo = SQLAlchemyWorkflowEventRepository(session)
        invocation_repo = SQLAlchemyWorkflowSpecialistInvocationRepository(session)
        approval_repo = SQLAlchemyWorkflowApprovalCheckpointRepository(session)

        assert isinstance(run_repo, WorkflowRunRepository)
        assert isinstance(step_repo, WorkflowStepRepository)
        assert isinstance(artifact_repo, WorkflowArtifactRepository)
        assert isinstance(event_repo, WorkflowEventRepository)
        assert isinstance(invocation_repo, WorkflowSpecialistInvocationRepository)
        assert isinstance(approval_repo, WorkflowApprovalCheckpointRepository)

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
        assert current_state.active_approval_checkpoint is None
        assert current_state.sync_records == ()


def test_workflow_sync_record_repository_enforces_durable_identity_and_lineage() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)

        assert isinstance(sync_repo, WorkflowSyncRecordRepository)

        run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_scheduling",
                status=WorkflowRunStatus.PENDING.value,
                current_step_name="apply_schedule",
                current_step_attempt=1,
                attempt_count=1,
            )
        )
        step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="apply_schedule",
                status=WorkflowStepStatus.PENDING.value,
                attempt_number=1,
            )
        )
        proposal = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=step.id,
                artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
                schema_version="2026-03-13",
                producer_step_name="dispatch_calendar_agent",
                payload=ScheduleProposalArtifactPayload(
                    proposal_summary="Apply a reviewed weekly schedule.",
                    calendar_id="primary",
                    time_blocks=(
                        {
                            "title": "Inbox triage",
                            "start": "2026-03-16T09:00:00Z",
                            "end": "2026-03-16T09:30:00Z",
                            "task_title": "Triage inbox",
                        },
                    ),
                    proposed_changes=("Create one task write and one calendar block.",),
                ).to_dict(),
            )
        )

        task_sync = sync_repo.create(
            NewWorkflowSyncRecord(
                run_id=run.id,
                step_id=step.id,
                proposal_artifact_id=proposal.id,
                proposal_version_number=proposal.version_number,
                target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
                sync_kind=WorkflowSyncKind.TASK_UPSERT.value,
                planned_item_key="task:triage-inbox",
                execution_order=1,
                idempotency_key=f"wf-sync:{proposal.id}:task:triage-inbox",
                payload_fingerprint="sha256:task-1",
                payload={"title": "Triage inbox", "summary": "Clear pending email."},
            )
        )
        calendar_sync = sync_repo.create(
            NewWorkflowSyncRecord(
                run_id=run.id,
                step_id=step.id,
                proposal_artifact_id=proposal.id,
                proposal_version_number=proposal.version_number,
                target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
                sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
                planned_item_key="calendar:focus-block-1",
                execution_order=2,
                idempotency_key=f"wf-sync:{proposal.id}:calendar:focus-block-1",
                payload_fingerprint="sha256:cal-1",
                payload={"title": "Inbox triage", "start": "2026-03-16T09:00:00Z"},
                supersedes_sync_record_id=task_sync.id,
            )
        )

        listed = sync_repo.list_for_run(run.id)
        assert [record.planned_item_key for record in listed] == [
            "task:triage-inbox",
            "calendar:focus-block-1",
        ]
        assert sync_repo.get_by_identity(
            proposal_artifact_id=proposal.id,
            proposal_version_number=proposal.version_number,
            target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
            sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
            planned_item_key="calendar:focus-block-1",
        ) == calendar_sync
        assert listed[1].supersedes_sync_record_id == task_sync.id
        assert sync_repo.list_for_proposal(proposal.id)[0].proposal_version_number == proposal.version_number


def test_workflow_sync_record_repository_queries_remaining_and_failed_items() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)

        run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_scheduling",
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name="apply_schedule",
                current_step_attempt=1,
                attempt_count=1,
            )
        )
        step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="apply_schedule",
                status=WorkflowStepStatus.RUNNING.value,
                attempt_number=1,
            )
        )
        proposal = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=step.id,
                artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
                schema_version="2026-03-13",
                producer_step_name="dispatch_calendar_agent",
                payload=ScheduleProposalArtifactPayload(
                    proposal_summary="Apply a reviewed weekly schedule.",
                    calendar_id="primary",
                    time_blocks=(),
                    proposed_changes=(),
                ).to_dict(),
            )
        )

        pending = sync_repo.create(
            NewWorkflowSyncRecord(
                run_id=run.id,
                step_id=step.id,
                proposal_artifact_id=proposal.id,
                proposal_version_number=proposal.version_number,
                target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
                sync_kind=WorkflowSyncKind.TASK_UPSERT.value,
                planned_item_key="task:triage-inbox",
                execution_order=1,
                idempotency_key=f"wf-sync:{proposal.id}:task:triage-inbox",
                payload_fingerprint="sha256:task-1",
                payload={"title": "Triage inbox"},
            )
        )
        failed = sync_repo.create(
            NewWorkflowSyncRecord(
                run_id=run.id,
                step_id=step.id,
                proposal_artifact_id=proposal.id,
                proposal_version_number=proposal.version_number,
                target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
                sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
                planned_item_key="calendar:focus-block-1",
                execution_order=2,
                idempotency_key=f"wf-sync:{proposal.id}:calendar:focus-block-1",
                payload_fingerprint="sha256:cal-1",
                payload={"title": "Inbox triage"},
                status=WorkflowSyncStatus.FAILED_RETRYABLE.value,
                last_error_summary="Calendar API timed out.",
            )
        )

        claimed = sync_repo.claim_next_pending(
            run_id=run.id,
            step_id=step.id,
            step_name=step.step_name,
            step_attempt_number=step.attempt_number,
        )
        assert claimed is not None
        assert claimed.id == pending.id
        assert claimed.status == WorkflowSyncStatus.IN_PROGRESS.value
        assert claimed.attempt_count == 1
        assert claimed.last_attempt_step_id == step.id

        completed = sync_repo.mark_succeeded(
            claimed.id,
            external_object_id="task-123",
            completed_at=datetime.now(UTC),
        )
        assert completed is not None
        assert completed.external_object_id == "task-123"

        remaining = sync_repo.list_remaining(WorkflowSyncRemainingQuery(run_id=run.id))
        assert [record.id for record in remaining] == [failed.id]
        failed_items = sync_repo.list_failed(WorkflowSyncFailedQuery(run_id=run.id))
        assert [record.id for record in failed_items] == [failed.id]


def test_workflow_sync_record_repository_retry_sync_items_by_step_attempt_lineage() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)

        run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_scheduling",
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name="apply_schedule",
                current_step_attempt=2,
                attempt_count=2,
            )
        )
        first_attempt = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="apply_schedule",
                status=WorkflowStepStatus.FAILED.value,
                attempt_number=1,
            )
        )
        second_attempt = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="apply_schedule",
                status=WorkflowStepStatus.RUNNING.value,
                attempt_number=2,
            )
        )
        other_step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="dispatch_calendar_agent",
                status=WorkflowStepStatus.SUCCEEDED.value,
                attempt_number=1,
            )
        )
        proposal = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=first_attempt.id,
                artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
                schema_version="2026-03-13",
                producer_step_name="dispatch_calendar_agent",
                payload=ScheduleProposalArtifactPayload(
                    proposal_summary="Apply a reviewed weekly schedule.",
                    calendar_id="primary",
                    time_blocks=(),
                    proposed_changes=(),
                ).to_dict(),
            )
        )

        retryable = sync_repo.create(
            NewWorkflowSyncRecord(
                run_id=run.id,
                step_id=first_attempt.id,
                proposal_artifact_id=proposal.id,
                proposal_version_number=proposal.version_number,
                target_system=WorkflowTargetSystem.TASK_SYSTEM.value,
                sync_kind=WorkflowSyncKind.TASK_UPSERT.value,
                planned_item_key="task:retryable",
                execution_order=1,
                idempotency_key=f"wf-sync:{proposal.id}:task:retryable",
                payload_fingerprint="sha256:retryable",
                payload={"title": "Retryable"},
                status=WorkflowSyncStatus.FAILED_RETRYABLE.value,
            )
        )
        sync_repo.create(
            NewWorkflowSyncRecord(
                run_id=run.id,
                step_id=first_attempt.id,
                proposal_artifact_id=proposal.id,
                proposal_version_number=proposal.version_number,
                target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
                sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
                planned_item_key="calendar:uncertain",
                execution_order=2,
                idempotency_key=f"wf-sync:{proposal.id}:calendar:uncertain",
                payload_fingerprint="sha256:uncertain",
                payload={"title": "Uncertain"},
                status=WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
            )
        )
        sync_repo.create(
            NewWorkflowSyncRecord(
                run_id=run.id,
                step_id=other_step.id,
                proposal_artifact_id=proposal.id,
                proposal_version_number=proposal.version_number,
                target_system=WorkflowTargetSystem.CALENDAR_SYSTEM.value,
                sync_kind=WorkflowSyncKind.CALENDAR_BLOCK_UPSERT.value,
                planned_item_key="calendar:other-step",
                execution_order=3,
                idempotency_key=f"wf-sync:{proposal.id}:calendar:other-step",
                payload_fingerprint="sha256:other-step",
                payload={"title": "Other step"},
                status=WorkflowSyncStatus.FAILED_RETRYABLE.value,
            )
        )

        scoped = sync_repo.list_for_step_attempt(
            WorkflowSyncStepQuery(
                run_id=run.id,
                step_name="apply_schedule",
                max_attempt_number=second_attempt.attempt_number,
            )
        )
        assert [record.planned_item_key for record in scoped] == [
            "task:retryable",
            "calendar:uncertain",
        ]

        claimed = sync_repo.claim_next_pending(
            run_id=run.id,
            step_id=second_attempt.id,
            step_name=second_attempt.step_name,
            step_attempt_number=second_attempt.attempt_number,
        )
        assert claimed is not None
        assert claimed.id == retryable.id
        assert claimed.last_attempt_step_id == second_attempt.id
        assert claimed.attempt_count == 1


def test_workflow_specialist_invocation_and_schedule_proposal_lineage() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        invocation_repo = SQLAlchemyWorkflowSpecialistInvocationRepository(session)

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
        schedule_step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="dispatch_calendar_agent",
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
        schedule_proposal = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=schedule_step.id,
                artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
                schema_version="2026-03-13",
                producer_step_name=schedule_step.step_name,
                lineage_parent_id=normalized_v2.id,
                payload=ScheduleProposalArtifactPayload(
                    proposal_summary="Schedule the reviewed tasks across the week.",
                    calendar_id="primary",
                    time_blocks=(
                        {
                            "title": "Triage inbox",
                            "start": "2026-03-16T09:00:00Z",
                            "end": "2026-03-16T09:30:00Z",
                        },
                    ),
                    proposed_changes=("Create one focused triage block on Monday morning.",),
                    warnings=("Deadline for draft priorities is still tentative.",),
                ).to_dict(),
            )
        )
        invocation = invocation_repo.create(
            NewWorkflowSpecialistInvocation(
                run_id=run.id,
                step_id=schedule_step.id,
                specialist_name="calendar_agent",
                input_artifact_id=normalized_v2.id,
            )
        )
        updated_invocation = invocation_repo.update(
            invocation.id,
            WorkflowSpecialistInvocationPatch(
                output_artifact_id=schedule_proposal.id,
                status="succeeded",
                completed_at=datetime.now(UTC),
            ),
        )
        summary_artifact = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=summarize_step.id,
                artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value,
                schema_version="2026-03-13",
                producer_step_name=summarize_step.step_name,
                lineage_parent_id=schedule_proposal.id,
                payload=WorkflowSummaryArtifactPayload(
                    request_artifact_id=request_artifact.id,
                    intermediate_artifact_ids=(normalized_v2.id, schedule_proposal.id),
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
        assert latest_by_type[WorkflowArtifactType.SCHEDULE_PROPOSAL.value].id == schedule_proposal.id
        assert latest_by_type[WorkflowArtifactType.FINAL_SUMMARY.value].id == summary_artifact.id

        assert updated_invocation is not None
        assert updated_invocation.input_artifact_id == normalized_v2.id
        assert updated_invocation.output_artifact_id == schedule_proposal.id
        assert updated_invocation.status == "succeeded"

        summary_payload = latest_by_type[WorkflowArtifactType.FINAL_SUMMARY.value].payload
        assert summary_payload["request_artifact_id"] == request_artifact.id
        assert summary_payload["intermediate_artifact_ids"] == [normalized_v2.id, schedule_proposal.id]
        assert summary_payload["validation_artifact_ids"] == [validation_artifact.id]
        assert summary_payload["approval_decision"] is None
        assert summary_payload["approval_decision_artifact_id"] is None
        assert summary_payload["downstream_sync_status"] is None
        assert summary_payload["downstream_sync_artifact_ids"] == []
        assert summary_payload["downstream_sync_reference_ids"] == []

        persisted_invocations = invocation_repo.list_for_run(run.id)
        assert [record.specialist_name for record in persisted_invocations] == ["calendar_agent"]


def test_workflow_approval_checkpoint_persists_pending_and_resolved_decisions() -> None:
    with _session() as session:
        run_repo = SQLAlchemyWorkflowRunRepository(session)
        step_repo = SQLAlchemyWorkflowStepRepository(session)
        artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        event_repo = SQLAlchemyWorkflowEventRepository(session)
        approval_repo = SQLAlchemyWorkflowApprovalCheckpointRepository(session)

        run = run_repo.create(
            NewWorkflowRun(
                workflow_type="weekly_scheduling",
                status=WorkflowRunStatus.BLOCKED.value,
                current_step_name="await_schedule_approval",
                current_step_attempt=1,
                attempt_count=3,
                needs_action=True,
                blocked_reason=WorkflowBlockedReason.APPROVAL_REQUIRED.value,
                resume_step_name="apply_schedule",
                resume_step_attempt=1,
            )
        )
        proposal_step = step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name="dispatch_calendar_agent",
                status=WorkflowStepStatus.SUCCEEDED.value,
                attempt_number=1,
                completed_at=datetime.now(UTC),
            )
        )
        proposal_artifact = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=proposal_step.id,
                artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
                schema_version="2026-03-13",
                producer_step_name=proposal_step.step_name,
                payload=ScheduleProposalArtifactPayload(
                    proposal_summary="Hold focus blocks and meeting windows for the week.",
                    calendar_id="primary",
                    time_blocks=(
                        {
                            "title": "Deep work",
                            "start": "2026-03-16T09:00:00Z",
                            "end": "2026-03-16T11:00:00Z",
                        },
                    ),
                    proposed_changes=("Reserve Monday and Tuesday mornings for deep work.",),
                ).to_dict(),
            )
        )
        checkpoint = approval_repo.create(
            NewWorkflowApprovalCheckpoint(
                run_id=run.id,
                step_id=proposal_step.id,
                target_artifact_id=proposal_artifact.id,
                resume_step_name="apply_schedule",
                allowed_actions=("approve", "reject", "request_revision"),
            )
        )
        approval_request = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=proposal_step.id,
                artifact_type=WorkflowArtifactType.APPROVAL_REQUEST.value,
                schema_version="2026-03-13",
                producer_step_name="await_schedule_approval",
                lineage_parent_id=proposal_artifact.id,
                payload=ApprovalRequestArtifactPayload(
                    checkpoint_id=checkpoint.id,
                    target_artifact_id=proposal_artifact.id,
                    target_version_number=proposal_artifact.version_number,
                    allowed_actions=("approve", "reject", "request_revision"),
                    pause_reason="Awaiting operator approval before downstream changes.",
                ).to_dict(),
            )
        )
        event_repo.create(
            NewWorkflowEvent(
                run_id=run.id,
                step_id=proposal_step.id,
                event_type="approval_checkpoint_created",
                run_status=WorkflowRunStatus.BLOCKED.value,
                step_status=WorkflowStepStatus.SUCCEEDED.value,
                summary="Approval checkpoint created for schedule proposal.",
                details={"checkpoint_id": checkpoint.id, "artifact_id": approval_request.id},
            )
        )

        active_state = run_repo.get_with_current_state(run.id)
        assert active_state is not None
        assert active_state.active_approval_checkpoint is not None
        assert active_state.active_approval_checkpoint.id == checkpoint.id
        assert active_state.active_approval_checkpoint.allowed_actions == [
            "approve",
            "reject",
            "request_revision",
        ]

        resolved = approval_repo.update(
            checkpoint.id,
            WorkflowApprovalCheckpointPatch(
                status="resolved",
                decision="request_revision",
                decision_actor="telegram:1",
                decision_at=datetime.now(UTC),
                revision_feedback="Keep Friday afternoon free.",
                resolved_at=datetime.now(UTC),
            ),
        )
        assert resolved is not None

        decision_artifact = artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                step_id=proposal_step.id,
                artifact_type=WorkflowArtifactType.APPROVAL_DECISION.value,
                schema_version="2026-03-13",
                producer_step_name="await_schedule_approval",
                lineage_parent_id=approval_request.id,
                payload=ApprovalDecisionArtifactPayload(
                    checkpoint_id=checkpoint.id,
                    target_artifact_id=proposal_artifact.id,
                    target_version_number=proposal_artifact.version_number,
                    decision="request_revision",
                    actor="telegram:1",
                    decision_at=resolved.decision_at,
                    revision_feedback="Keep Friday afternoon free.",
                ).to_dict(),
            )
        )

        current_state = run_repo.get_with_current_state(run.id)
        assert current_state is not None
        assert current_state.run.blocked_reason == WorkflowBlockedReason.APPROVAL_REQUIRED.value
        assert current_state.active_approval_checkpoint is None
        assert len(current_state.approval_checkpoints) == 1
        assert current_state.approval_checkpoints[0].target_artifact_id == proposal_artifact.id
        assert current_state.latest_artifacts[WorkflowArtifactType.APPROVAL_DECISION.value].id == (
            decision_artifact.id
        )
        assert current_state.last_event is not None
        assert current_state.last_event.event_type == "approval_checkpoint_created"


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
