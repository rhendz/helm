from datetime import UTC, datetime

from helm_api.services.workflow_status_service import (
    WorkflowRunCreateInput,
    WorkflowStatusService,
    build_workflow_run_create_input,
)
from helm_telegram_bot import main as telegram_main
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService
from helm_orchestration import (
    ApprovalAction,
    ApprovalDecision,
    CalendarAgentInput,
    CalendarAgentOutput,
    CalendarSyncResult,
    NormalizedTaskArtifact,
    PreparedSpecialistInput,
    ScheduleBlock,
    SyncOutcomeStatus,
    SyncRetryDisposition,
    ScheduleProposalValidator,
    SpecialistName,
    TaskAgentInput,
    TaskAgentOutput,
    TaskArtifact,
    TaskSyncResult,
    ValidationOutcome,
    ExecutionFailurePayload,
    NormalizedTaskValidator,
    RegisteredValidator,
    RetryState,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowArtifactKind,
    WorkflowOrchestrationService,
    WorkflowResumeService,
    WorkflowSpecialistStep,
)
from helm_storage.db import Base
from helm_storage.repositories import (
    SQLAlchemyWorkflowSyncRecordRepository,
    WorkflowArtifactType,
    WorkflowSyncRecoveryClassification,
    WorkflowSyncRecordPatch,
    WorkflowSyncStatus,
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
    return build_workflow_run_create_input(
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
        validator_registry=_validator_registry(),
    )


def _validator_registry() -> ValidatorRegistry:
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


class _RecordingTaskAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def upsert_task(self, request):  # noqa: ANN001
        self.calls.append(("upsert", request.item.planned_item_key))
        return TaskSyncResult(
            status=SyncOutcomeStatus.SUCCEEDED,
            external_object_id=f"task-{request.item.planned_item_key}",
            retry_disposition=SyncRetryDisposition.TERMINAL,
        )

    def reconcile_task(self, request):  # noqa: ANN001
        raise AssertionError("Task reconcile not expected in workflow status tests.")


class _RecordingCalendarAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._outcomes: dict[str, CalendarSyncResult] = {}

    def set_upsert_outcome(self, planned_item_key: str, outcome: CalendarSyncResult) -> None:
        self._outcomes[planned_item_key] = outcome

    def upsert_calendar_block(self, request):  # noqa: ANN001
        self.calls.append(("upsert", request.item.planned_item_key))
        return self._outcomes.get(
            request.item.planned_item_key,
            CalendarSyncResult(
                status=SyncOutcomeStatus.SUCCEEDED,
                external_object_id=f"event-{request.item.planned_item_key}",
                retry_disposition=SyncRetryDisposition.TERMINAL,
            ),
        )

    def reconcile_calendar_block(self, request):  # noqa: ANN001
        raise AssertionError("Calendar reconcile not expected in workflow status tests.")


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

    def _handler(payload: object) -> CalendarAgentOutput:
        CalendarAgentInput.model_validate(payload)
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
            proposed_changes=(
                "Create a Monday morning triage block.",
                "Reserve one review slot for drafting priorities.",
            ),
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


def _approved_sync_run(session: Session) -> tuple[int, WorkflowOrchestrationService, _RecordingCalendarAdapter]:
    task_adapter = _RecordingTaskAdapter()
    calendar_adapter = _RecordingCalendarAdapter()
    service = WorkflowOrchestrationService(
        session,
        validator_registry=_validator_registry(),
        task_system_adapter=task_adapter,
        calendar_system_adapter=calendar_adapter,
    )
    created = service.create_run(
        workflow_type="weekly_scheduling",
        first_step_name="dispatch_task_agent",
        request_payload={
            "request_text": "Plan my week around deep work.",
            "submitted_by": "telegram:user",
            "channel": "telegram",
            "metadata": {"chat_id": "123"},
        },
    )
    service.execute_specialist_step(created.run.id, _task_agent_step())
    blocked = WorkflowResumeService(
        session,
        workflow_service=service,
        specialist_steps={_calendar_agent_step().key: _calendar_agent_step()},
    ).resume_run(created.run.id)
    target_artifact_id = blocked.active_approval_checkpoint.target_artifact_id  # type: ignore[union-attr]
    approved = service.submit_approval_decision(
        blocked.run.id,
        decision=ApprovalDecision(
            action=ApprovalAction.APPROVE,
            actor="telegram:user",
            target_artifact_id=target_artifact_id,
        ),
    )
    return approved.run.id, service, calendar_adapter


def test_create_run_summary_answers_operator_triage_question() -> None:
    with _session() as session:
        service = WorkflowStatusService(session)

        created = service.create_run(
            build_workflow_run_create_input(
                workflow_type="weekly_scheduling",
                first_step_name="dispatch_task_agent",
                request_text=(
                    "Plan my week. Tasks: Finish roadmap draft high due Wednesday 90m; "
                    "Prep interviews medium 120m. Constraints: protect deep work mornings; keep Friday afternoon open."
                ),
                submitted_by="telegram:user",
                channel="telegram",
                metadata={"chat_id": "123"},
            )
        )

        assert created["workflow_type"] == "weekly_scheduling"
        assert created["status"] == WorkflowRunStatus.PENDING.value
        assert created["current_step"] == "dispatch_task_agent"
        assert created["paused_state"] is None
        assert created["needs_action"] is False
        assert created["last_event_summary"] == "Workflow run created"
        assert created["available_actions"] == []
        assert created["weekly_request"]["tasks"][0]["title"] == "Finish roadmap draft"
        assert created["weekly_request"]["protected_time"] == ["protect deep work mornings"]
        assert created["weekly_request"]["no_meeting_windows"] == ["keep Friday afternoon open."]


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
        assert summary["approval_checkpoint"]["time_blocks"][0]["title"] == "Deep work"
        assert summary["approval_checkpoint"]["proposed_changes"] == [
            "Reserve Monday and Tuesday mornings for deep work."
        ]
        assert summary["approval_checkpoint"]["target_version_number"] == 1
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
        assert summary["latest_proposal_version"]["artifact_id"] == summary["approval_checkpoint"]["target_artifact_id"]
        assert summary["proposal_versions"][0]["is_actionable"] is True


def test_effect_summary_projects_pending_approved_write_counts_before_execution() -> None:
    with _session() as session:
        run_id, _service, _calendar_adapter = _approved_sync_run(session)

        summary = WorkflowStatusService(session).get_run_detail(run_id)

        assert summary is not None
        assert summary["effect_summary"] == {
            "pending_execution": True,
            "total_writes": 2,
            "task_writes": 1,
            "calendar_writes": 1,
        }
        assert summary["sync"]["counts_by_state"] == {WorkflowSyncStatus.PENDING.value: 2}
        assert summary["sync"]["counts_by_target"] == {
            "task_system": 1,
            "calendar_system": 1,
        }
        assert summary["failure_summary"] == "Approved writes are queued and ready for execution."
        assert summary["safe_next_actions"] == [
            {"action": "await_execution", "label": "Await approved write execution"}
        ]
        assert summary["completion_summary"]["headline"] == "Approved schedule is queued to sync 2 planned write(s)."
        assert summary["completion_summary"]["scheduled_highlights"] == ["Triage inbox"]


def test_completed_sync_summary_surfaces_explicit_replay_action_for_successful_lineage() -> None:
    with _session() as session:
        run_id, orchestration, _calendar_adapter = _approved_sync_run(session)
        completed = orchestration.execute_pending_sync_step(run_id)

        summary = WorkflowStatusService(session).get_run_detail(completed.run.id)

        assert summary is not None
        assert summary["status"] == WorkflowRunStatus.COMPLETED.value
        assert summary["failure_kind"] is None
        assert summary["recovery_class"] is None
        assert summary["safe_next_actions"] == [
            {"action": "request_replay", "label": "Request explicit replay after adapter fix"}
        ]
        assert summary["completion_summary"]["headline"] == "Scheduled 1 block(s) and synced 2 approved write(s)."
        assert summary["completion_summary"]["downstream_sync_status"] == "succeeded"


def test_sync_summary_projects_recoverable_failure_and_replay_lineage() -> None:
    with _session() as session:
        run_id, orchestration, _calendar_adapter = _approved_sync_run(session)
        sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
        failed_record = sync_repo.list_for_run(run_id)[1]
        sync_repo.update(
            failed_record.id,
            WorkflowSyncRecordPatch(
                status=WorkflowSyncStatus.FAILED_RETRYABLE.value,
                last_error_summary="Calendar API timed out.",
                recovery_classification=WorkflowSyncRecoveryClassification.RECOVERABLE_FAILURE.value,
            ),
        )
        replay_state = orchestration.request_sync_replay(
            run_id,
            actor="telegram:user",
            sync_record_ids=(failed_record.id,),
            reason="Replay after adapter timeout.",
        )

        summary = WorkflowStatusService(session).get_run_detail(replay_state.run.id)

        assert summary is not None
        assert summary["failure_kind"] == WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value
        assert summary["recovery_class"] == WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value
        assert summary["retryable"] is True
        assert summary["sync"]["last_failed_or_unresolved"]["planned_item_key"] == "calendar:inbox-triage:1"
        assert summary["sync"]["replay_lineage"]["source_sync_record_ids"] == [failed_record.id]
        assert summary["sync"]["replay_lineage"]["latest_generation"] == 1
        assert summary["safe_next_actions"] == [
            {"action": "await_replay", "label": "Await replay processing"}
        ]


def test_terminal_sync_failure_projects_terminal_recovery_without_event_parsing() -> None:
    with _session() as session:
        run_id, _orchestration, _calendar_adapter = _approved_sync_run(session)
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

        summary = WorkflowStatusService(session).get_run_detail(run_id)

        assert summary is not None
        assert summary["failure_kind"] == WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value
        assert summary["failure_summary"] == "Calendar rejected the payload as invalid."
        assert summary["retryable"] is False
        assert summary["safe_next_actions"] == [
            {"action": "request_replay", "label": "Request explicit replay after adapter fix"}
        ]
        assert summary["sync"]["counts_by_state"] == {
            WorkflowSyncStatus.PENDING.value: 1,
            WorkflowSyncStatus.FAILED_TERMINAL.value: 1,
        }
        assert summary["sync"]["last_failed_or_unresolved"]["status"] == WorkflowSyncStatus.FAILED_TERMINAL.value


def test_partial_sync_summary_stays_visible_after_termination() -> None:
    with _session() as session:
        run_id, orchestration, calendar_adapter = _approved_sync_run(session)
        calendar_adapter.set_upsert_outcome(
            "calendar:inbox-triage:1",
            CalendarSyncResult(
                status=SyncOutcomeStatus.RETRYABLE_FAILURE,
                retry_disposition=SyncRetryDisposition.RETRYABLE,
                error_summary="Calendar API timed out.",
            ),
        )
        failed = orchestration.execute_pending_sync_step(run_id)
        terminated = orchestration.terminate_run(
            failed.run.id,
            reason="Operator revoked approval after partial sync.",
        )

        summary = WorkflowStatusService(session).get_run_detail(terminated.run.id)

        assert summary is not None
        assert summary["status"] == WorkflowRunStatus.TERMINATED.value
        assert summary["failure_kind"] == (
            WorkflowSyncRecoveryClassification.TERMINATED_AFTER_PARTIAL_SUCCESS.value
        )
        assert summary["failure_summary"] == "Remaining approved writes were cancelled after partial sync success."
        assert summary["retryable"] is False
        assert summary["safe_next_actions"] == [
            {"action": "request_replay", "label": "Request replay for cancelled writes"}
        ]
        assert summary["sync"]["counts_by_state"] == {
            WorkflowSyncStatus.SUCCEEDED.value: 1,
            WorkflowSyncStatus.CANCELLED.value: 1,
        }
        assert summary["sync"]["last_failed_or_unresolved"]["planned_item_key"] == "calendar:inbox-triage:1"
        assert summary["sync"]["last_failed_or_unresolved"]["recovery_class"] == (
            WorkflowSyncRecoveryClassification.TERMINATED_AFTER_PARTIAL_SUCCESS.value
        )


def test_status_projection_contract_stays_stable_after_replay_on_terminated_run() -> None:
    with _session() as session:
        run_id, orchestration, calendar_adapter = _approved_sync_run(session)
        calendar_adapter.set_upsert_outcome(
            "calendar:inbox-triage:1",
            CalendarSyncResult(
                status=SyncOutcomeStatus.RETRYABLE_FAILURE,
                retry_disposition=SyncRetryDisposition.RETRYABLE,
                error_summary="Calendar API timed out.",
            ),
        )
        failed = orchestration.execute_pending_sync_step(run_id)
        terminated = orchestration.terminate_run(
            failed.run.id,
            reason="Operator froze remaining writes after partial sync.",
        )
        cancelled_record = SQLAlchemyWorkflowSyncRecordRepository(session).list_for_run(terminated.run.id)[1]
        replay_state = orchestration.request_sync_replay(
            terminated.run.id,
            actor="telegram:user",
            sync_record_ids=(cancelled_record.id,),
            reason="Replay cancelled calendar write with preserved lineage.",
        )

        summary = WorkflowStatusService(session).get_run_detail(replay_state.run.id)

        assert summary is not None
        assert set(summary["sync"]) == {
            "counts_by_state",
            "counts_by_target",
            "last_failed_or_unresolved",
            "replay_lineage",
        }
        assert set(summary["effect_summary"]) == {
            "pending_execution",
            "total_writes",
            "task_writes",
            "calendar_writes",
        }
        assert summary["sync"]["counts_by_state"] == {
            WorkflowSyncStatus.SUCCEEDED.value: 1,
            WorkflowSyncStatus.CANCELLED.value: 1,
            WorkflowSyncStatus.PENDING.value: 1,
        }
        assert summary["sync"]["replay_lineage"]["latest_generation"] == 1
        assert summary["sync"]["replay_lineage"]["source_sync_record_ids"] == [cancelled_record.id]
        assert summary["safe_next_actions"] == [
            {"action": "await_replay", "label": "Await replay processing"}
        ]


def test_run_detail_projects_latest_first_proposal_versions_and_decision_lineage() -> None:
    with _session() as session:
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
        first_blocked = orchestration.complete_current_step(
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
        target_artifact_id = first_blocked.active_approval_checkpoint.target_artifact_id  # type: ignore[union-attr]
        orchestration.submit_approval_decision(
            first_blocked.run.id,
            decision=ApprovalDecision(
                action=ApprovalAction.REQUEST_REVISION,
                actor="telegram:user",
                target_artifact_id=target_artifact_id,
                revision_feedback="Keep Friday afternoon open.",
            ),
        )
        second_blocked = orchestration.complete_current_step(
            created.run.id,
            artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
            artifact_payload={
                "proposal_summary": "Keep Friday afternoon open and focus mornings on deep work.",
                "calendar_id": "primary",
                "time_blocks": [
                    {
                        "title": "Deep work",
                        "start": "2026-03-16T09:00:00Z",
                        "end": "2026-03-16T11:00:00Z",
                    }
                ],
                "proposed_changes": ["Keep Friday afternoon open.", "Reserve Monday and Tuesday mornings for deep work."],
            },
            next_step_name="apply_schedule",
        )
        latest_artifact_id = second_blocked.active_approval_checkpoint.target_artifact_id  # type: ignore[union-attr]
        orchestration.submit_approval_decision(
            second_blocked.run.id,
            decision=ApprovalDecision(
                action=ApprovalAction.APPROVE,
                actor="telegram:user",
                target_artifact_id=latest_artifact_id,
            ),
        )

        detail = WorkflowStatusService(session).get_run_detail(created.run.id)

        assert detail is not None
        assert [item["version_number"] for item in detail["proposal_versions"]] == [2, 1]
        assert detail["proposal_versions"][0]["approved"] is True
        assert detail["proposal_versions"][0]["latest_decision"]["target_artifact_id"] == latest_artifact_id
        assert detail["proposal_versions"][0]["proposed_changes"] == [
            "Keep Friday afternoon open.",
            "Reserve Monday and Tuesday mornings for deep work.",
        ]
        assert detail["proposal_versions"][1]["superseded"] is True
        assert detail["proposal_versions"][1]["revision_feedback_summary"] == "Keep Friday afternoon open."


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
        run_id, orchestration, _calendar_adapter = _approved_sync_run(session)
        completed = orchestration.execute_pending_sync_step(run_id)

        detail = WorkflowStatusService(session).get_run_detail(completed.run.id)

        assert detail is not None
        assert detail["status"] == WorkflowRunStatus.COMPLETED.value
        assert detail["lineage"]["final_summary"]["request_artifact_id"] is not None
        assert detail["lineage"]["final_summary"]["approval_decision"] == ApprovalAction.APPROVE.value
        assert detail["lineage"]["final_summary"]["approval_decision_artifact_id"] is not None
        assert detail["lineage"]["final_summary"]["downstream_sync_status"] == "succeeded"
        assert len(detail["lineage"]["final_summary"]["downstream_sync_artifact_ids"]) == 2
        assert detail["lineage"]["final_summary"]["downstream_sync_reference_ids"][0].startswith("task_system:")
        assert detail["completion_summary"]["headline"] == "Scheduled 1 block(s) and synced 2 approved write(s)."
        assert detail["completion_summary"]["total_sync_writes"] == 2
        assert detail["completion_summary"]["attention_items"] == []


def test_completed_then_replayed_run_projects_live_recovery_over_stale_success_summary() -> None:
    with _session() as session:
        run_id, orchestration, _calendar_adapter = _approved_sync_run(session)
        completed = orchestration.execute_pending_sync_step(run_id)
        original_calendar_record = SQLAlchemyWorkflowSyncRecordRepository(session).list_for_run(completed.run.id)[1]

        replayed = orchestration.request_sync_replay(
            completed.run.id,
            actor="telegram:user",
            sync_record_ids=(original_calendar_record.id,),
            reason="Replay completed schedule after downstream adapter drift.",
        )
        detail = WorkflowStatusService(session).get_run_detail(replayed.run.id)

        assert detail is not None
        assert detail["status"] == WorkflowRunStatus.COMPLETED.value
        assert detail["recovery_class"] == WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value
        assert detail["failure_kind"] == WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value
        assert detail["lineage"]["final_summary"]["downstream_sync_status"] == "succeeded"
        assert detail["completion_summary"]["headline"] == (
            "Approved schedule needs downstream follow-up after 3 planned write(s)."
        )
        assert detail["completion_summary"]["downstream_sync_status"] == (
            WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value
        )
        assert detail["completion_summary"]["total_sync_writes"] == 3
        assert detail["completion_summary"]["attention_items"] == [
            "Replay requested for downstream sync lineage.",
            "Next: Await replay processing.",
        ]
        assert detail["safe_next_actions"] == [
            {"action": "await_replay", "label": "Await replay processing"}
        ]
        assert detail["sync"]["replay_lineage"]["source_sync_record_ids"] == [original_calendar_record.id]


def test_telegram_service_replay_wrapper_uses_shared_replay_request(monkeypatch) -> None:  # noqa: ANN001
    seen: dict[str, object] = {}

    def _request(*, run_id: int, actor: str, reason: str) -> dict[str, object]:
        seen.update({"run_id": run_id, "actor": actor, "reason": reason})
        return {
            "status": "accepted",
            "run_id": run_id,
            "source_sync_record_ids": [8],
            "replay_sync_record_ids": [13],
            "replay_queue_source_ids": [f"{run_id}:8"],
            "run": {
                "id": run_id,
                "status": "failed",
                "current_step": "apply_schedule",
                "paused_state": "awaiting_retry",
                "last_event_summary": "Explicit sync replay requested.",
                "needs_action": True,
                "available_actions": [],
                "safe_next_actions": [
                    {"action": "await_replay", "label": "Await replay processing"}
                ],
            },
            "reason": None,
        }

    monkeypatch.setattr(
        "helm_telegram_bot.services.workflow_status_service.request_workflow_run_replay",
        _request,
    )

    result = TelegramWorkflowStatusService().request_replay(
        21,
        actor="telegram:1",
        reason="Replay after adapter fix.",
    )

    assert seen == {
        "run_id": 21,
        "actor": "telegram:1",
        "reason": "Replay after adapter fix.",
    }
    assert result["id"] == 21
    assert result["safe_next_actions"] == [
        {"action": "await_replay", "label": "Await replay processing"}
    ]


def test_telegram_main_registers_workflow_replay_command(monkeypatch) -> None:  # noqa: ANN001
    registered: list[str] = []

    class _Application:
        def add_handler(self, handler) -> None:  # noqa: ANN001
            registered.append(next(iter(handler.commands)))

        def run_polling(self) -> None:
            return

    class _Builder:
        def token(self, _token: str) -> "_Builder":
            return self

        def build(self) -> _Application:
            return _Application()

    class _ApplicationFactory:
        @staticmethod
        def builder() -> _Builder:
            return _Builder()

    monkeypatch.setattr(telegram_main, "Application", _ApplicationFactory)
    monkeypatch.setattr(
        telegram_main,
        "get_settings",
        lambda: type("Settings", (), {"telegram_bot_token": "token"})(),
    )
    monkeypatch.setattr(telegram_main, "setup_logging", lambda: None)
    monkeypatch.setattr(
        telegram_main,
        "get_logger",
        lambda _name: type("Logger", (), {"info": lambda self, _event: None})(),
    )

    telegram_main.main()

    assert "workflow_replay" in registered
