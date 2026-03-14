from fastapi.testclient import TestClient
from helm_api.main import app
from helm_api.services import replay_service
from helm_observability import agent_runs as agent_run_observability
from helm_orchestration import (
    ApprovalAction,
    ApprovalDecision,
    CalendarAgentInput,
    CalendarAgentOutput,
    CalendarSyncResult,
    NormalizedTaskArtifact,
    NormalizedTaskValidator,
    PreparedSpecialistInput,
    RegisteredValidator,
    ScheduleBlock,
    ScheduleProposalValidator,
    SpecialistName,
    SyncOutcomeStatus,
    SyncRetryDisposition,
    TaskAgentInput,
    TaskAgentOutput,
    TaskArtifact,
    TaskSyncResult,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowArtifactKind,
    WorkflowOrchestrationService,
    WorkflowResumeService,
    WorkflowSpecialistStep,
)
from helm_storage.db import Base
from helm_storage.models import AgentRunORM, ReplayQueueORM
from helm_storage.repositories import (
    SQLAlchemyWorkflowSyncRecordRepository,
    WorkflowArtifactType,
    WorkflowSyncRecordPatch,
    WorkflowSyncRecoveryClassification,
    WorkflowSyncStatus,
)
from helm_worker.jobs import replay as replay_job
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class _RecordingTaskAdapter:
    def upsert_task(self, request):  # noqa: ANN001
        return TaskSyncResult(
            status=SyncOutcomeStatus.SUCCEEDED,
            external_object_id=f"task-{request.item.planned_item_key}",
            retry_disposition=SyncRetryDisposition.TERMINAL,
        )

    def reconcile_task(self, request):  # noqa: ANN001
        raise AssertionError("Task reconcile not expected in replay service tests.")


class _RecordingCalendarAdapter:
    def upsert_calendar_block(self, request):  # noqa: ANN001
        return CalendarSyncResult(
            status=SyncOutcomeStatus.SUCCEEDED,
            external_object_id=f"event-{request.item.planned_item_key}",
            retry_disposition=SyncRetryDisposition.TERMINAL,
        )

    def reconcile_calendar_block(self, request):  # noqa: ANN001
        raise AssertionError("Calendar reconcile not expected in replay service tests.")


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _validator_registry() -> ValidatorRegistry:
    return ValidatorRegistry(
        [
            RegisteredValidator(
                target=ValidatorTarget(kind=ValidationTargetKind.STEP_NAME, value="normalize_request"),
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


def _task_agent_step() -> WorkflowSpecialistStep:
    def _build_input(state) -> PreparedSpecialistInput:  # type: ignore[no-untyped-def]
        request_artifact = state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
        request = TaskAgentInput(
            workflow_type=state.run.workflow_type,
            run_id=state.run.id,
            step_name="dispatch_task_agent",
            request_artifact_id=request_artifact.id,
            request_text=request_artifact.payload["request_text"],
            submitted_by=request_artifact.payload["submitted_by"],
            channel=request_artifact.payload["channel"],
            metadata=request_artifact.payload["metadata"],
            constraints=(),
        )
        return PreparedSpecialistInput(input_artifact_id=request_artifact.id, payload=request)

    def _handler(payload: object) -> TaskAgentOutput:
        request = TaskAgentInput.model_validate(payload)
        return TaskAgentOutput(
            title="Weekly planning",
            summary=f"Normalize request: {request.request_text}",
            tasks=(
                TaskArtifact(
                    title="Triage inbox",
                    summary="Clear pending email and categorize follow-ups.",
                    priority="high",
                    estimated_minutes=30,
                ),
            ),
            warnings=(),
        )

    return WorkflowSpecialistStep(
        workflow_type="weekly_scheduling",
        step_name="dispatch_task_agent",
        specialist=SpecialistName.TASK_AGENT,
        input_builder=_build_input,
        handler=_handler,
        artifact_type=WorkflowArtifactKind.NORMALIZED_TASK,
        next_step_name="dispatch_calendar_agent",
    )


def _calendar_agent_step() -> WorkflowSpecialistStep:
    def _build_input(state) -> PreparedSpecialistInput:  # type: ignore[no-untyped-def]
        normalized_artifact = state.latest_artifacts[WorkflowArtifactType.NORMALIZED_TASK.value]
        request_artifact = state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
        normalized = NormalizedTaskArtifact.model_validate(normalized_artifact.payload)
        request = CalendarAgentInput(
            workflow_type=state.run.workflow_type,
            run_id=state.run.id,
            step_name="dispatch_calendar_agent",
            normalized_task_artifact_id=normalized_artifact.id,
            tasks=normalized.tasks,
            scheduling_constraints=("Protect deep work mornings.",),
            source_context={"chat_id": request_artifact.payload["metadata"]["chat_id"]},
            request_text=request_artifact.payload["request_text"],
            warnings=normalized.warnings,
            revision_request_artifact_id=None,
            revision_feedback=None,
            prior_proposal_artifact_id=None,
            prior_proposal_version=None,
        )
        return PreparedSpecialistInput(input_artifact_id=normalized_artifact.id, payload=request)

    def _handler(_payload: object) -> CalendarAgentOutput:
        return CalendarAgentOutput(
            proposal_summary="Draft a focused weekly schedule from validated tasks.",
            calendar_id="primary",
            time_blocks=(
                ScheduleBlock(
                    title="Inbox triage",
                    task_title="Triage inbox",
                    start="2026-03-16T09:00:00Z",
                    end="2026-03-16T09:30:00Z",
                ),
            ),
            proposed_changes=("Create a Monday morning triage block.",),
            warnings=(),
        )

    return WorkflowSpecialistStep(
        workflow_type="weekly_scheduling",
        step_name="dispatch_calendar_agent",
        specialist=SpecialistName.CALENDAR_AGENT,
        input_builder=_build_input,
        handler=_handler,
        artifact_type=WorkflowArtifactKind.SCHEDULE_PROPOSAL,
        next_step_name="apply_schedule",
    )


def _approved_sync_run(session: Session) -> int:
    service = WorkflowOrchestrationService(session, validator_registry=_validator_registry())
    created = service.create_run(
        workflow_type="weekly_scheduling",
        first_step_name="dispatch_task_agent",
        request_payload={
            "request_text": "Plan my week around deep work.",
            "submitted_by": "api:operator",
            "channel": "api",
            "metadata": {"chat_id": "123"},
        },
    )
    service.execute_specialist_step(created.run.id, _task_agent_step())
    blocked = WorkflowResumeService(
        session,
        workflow_service=service,
        specialist_steps={_calendar_agent_step().key: _calendar_agent_step()},
    ).resume_run(created.run.id)
    checkpoint = blocked.active_approval_checkpoint
    assert checkpoint is not None
    approved = service.submit_approval_decision(
        blocked.run.id,
        decision=ApprovalDecision(
            action=ApprovalAction.APPROVE,
            actor="api:operator",
            target_artifact_id=checkpoint.target_artifact_id,
        ),
    )
    return approved.run.id


def _completed_sync_run(session: Session) -> int:
    run_id = _approved_sync_run(session)
    WorkflowOrchestrationService(
        session,
        validator_registry=_validator_registry(),
        task_system_adapter=_RecordingTaskAdapter(),
        calendar_system_adapter=_RecordingCalendarAdapter(),
    ).execute_pending_sync_step(run_id)
    return run_id


def test_api_workflow_replay_endpoint_requests_explicit_replay(monkeypatch) -> None:  # noqa: ANN001
    _engine, session_local = _session_factory()
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    with session_local() as session:
        run_id = _approved_sync_run(session)
        sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
        failed_record = sync_repo.list_for_run(run_id)[1]
        sync_repo.update(
            failed_record.id,
            WorkflowSyncRecordPatch(
                status=WorkflowSyncStatus.FAILED_TERMINAL.value,
                last_error_summary="Calendar rejected the payload as invalid.",
                recovery_classification=WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value,
            ),
        )

    client = TestClient(app)
    response = client.post(
        f"/v1/replay/workflow-runs/{run_id}",
        json={"actor": "api:operator", "reason": "Replay after adapter fix."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["run_id"] == run_id
    assert payload["source_sync_record_ids"] == [failed_record.id]
    assert payload["replay_queue_source_ids"] == [f"{run_id}:{failed_record.id}"]
    assert payload["run"]["safe_next_actions"] == [
        {"action": "await_replay", "label": "Await replay processing"}
    ]
    assert payload["run"]["completion_summary"]["headline"] == (
        "Approved schedule needs downstream follow-up after 3 planned write(s)."
    )
    assert payload["run"]["sync"]["replay_lineage"]["source_sync_record_ids"] == [failed_record.id]


def test_completed_run_replay_leaves_durable_recovery_truth_for_shared_projection() -> None:
    _engine, session_local = _session_factory()

    with session_local() as session:
        run_id = _completed_sync_run(session)
        original_calendar_record = SQLAlchemyWorkflowSyncRecordRepository(session).list_for_run(run_id)[1]

        replayed = WorkflowOrchestrationService(session, validator_registry=_validator_registry()).request_sync_replay(
            run_id,
            actor="api:operator",
            sync_record_ids=(original_calendar_record.id,),
            reason="Replay completed run after adapter drift.",
        )
        sync_records = SQLAlchemyWorkflowSyncRecordRepository(session).list_for_run(replayed.run.id)
        final_summary = replayed.latest_artifacts[WorkflowArtifactType.FINAL_SUMMARY.value]

        assert replayed.run.status == "completed"
        assert sync_records[1].status == WorkflowSyncStatus.SUCCEEDED.value
        assert sync_records[1].recovery_classification == (
            WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value
        )
        assert sync_records[-1].status == WorkflowSyncStatus.PENDING.value
        assert sync_records[-1].replayed_from_sync_record_id == original_calendar_record.id
        assert sync_records[-1].recovery_classification == (
            WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value
        )
        assert final_summary.version_number == 2
        assert final_summary.payload["downstream_sync_status"] == "pending"
        assert len(final_summary.payload["downstream_sync_artifact_ids"]) == 3


def test_api_workflow_replay_endpoint_accepts_completed_successful_representative_run(monkeypatch) -> None:  # noqa: ANN001
    _engine, session_local = _session_factory()
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    with session_local() as session:
        run_id = _completed_sync_run(session)
        source_sync_record_ids = [
            record.id
            for record in SQLAlchemyWorkflowSyncRecordRepository(session).list_for_run(run_id)
            if record.replayed_from_sync_record_id is None
        ]

    client = TestClient(app)
    response = client.post(
        f"/v1/replay/workflow-runs/{run_id}",
        json={"actor": "api:operator", "reason": "Replay completed run after adapter drift."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["run_id"] == run_id
    assert payload["source_sync_record_ids"] == source_sync_record_ids
    assert payload["replay_queue_source_ids"] == [f"{run_id}:{sync_record_id}" for sync_record_id in source_sync_record_ids]
    assert payload["run"]["recovery_class"] == WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value
    assert payload["run"]["safe_next_actions"] == [
        {"action": "await_replay", "label": "Await replay processing"}
    ]
    assert payload["run"]["completion_summary"]["headline"] == (
        "Approved schedule needs downstream follow-up after 4 planned write(s)."
    )
    assert payload["run"]["sync"]["replay_lineage"]["source_sync_record_ids"] == source_sync_record_ids


def test_api_workflow_replay_endpoint_rejects_retryable_sync_failures(monkeypatch) -> None:  # noqa: ANN001
    _engine, session_local = _session_factory()
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    with session_local() as session:
        run_id = _approved_sync_run(session)
        sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
        failed_record = sync_repo.list_for_run(run_id)[1]
        sync_repo.update(
            failed_record.id,
            WorkflowSyncRecordPatch(
                status=WorkflowSyncStatus.FAILED_RETRYABLE.value,
                last_error_summary="Calendar timed out.",
                recovery_classification=WorkflowSyncRecoveryClassification.RECOVERABLE_FAILURE.value,
            ),
        )

    client = TestClient(app)
    response = client.post(
        f"/v1/replay/workflow-runs/{run_id}",
        json={"actor": "api:operator", "reason": "Trying replay instead of retry."},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == f"Workflow run {run_id} does not allow explicit replay."


def test_worker_replay_job_hands_workflow_sync_replays_to_shared_service(monkeypatch) -> None:  # noqa: ANN001
    _engine, session_local = _session_factory()
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)
    monkeypatch.setattr(replay_job, "SessionLocal", session_local)
    monkeypatch.setattr(agent_run_observability, "SessionLocal", session_local)

    seen: list[str] = []

    def _execute(*, source_id: str) -> dict[str, object]:
        seen.append(source_id)
        return {"status": "accepted", "source_id": source_id}

    monkeypatch.setattr(replay_service, "execute_workflow_sync_replay", _execute)

    with session_local() as session:
        run_id = _approved_sync_run(session)
        sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
        failed_record = sync_repo.list_for_run(run_id)[1]
        sync_repo.update(
            failed_record.id,
            WorkflowSyncRecordPatch(
                status=WorkflowSyncStatus.FAILED_TERMINAL.value,
                recovery_classification=WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value,
            ),
        )
        replay_service.request_workflow_run_replay(
            run_id=run_id,
            actor="api:operator",
            reason="Replay after adapter fix.",
        )
        replay_item = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.source_type == "workflow_sync_replay")
        ).scalar_one()

    replay_job.run()

    with session_local() as session:
        replay_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == replay_item.id)
        ).scalar_one()
        agent_runs = list(session.execute(select(AgentRunORM)).scalars().all())

    assert seen == [f"{run_id}:{failed_record.id}"]
    assert replay_row.status == "completed"
    assert replay_row.attempts == 1
    assert len(agent_runs) == 1
    assert agent_runs[0].status == "succeeded"
