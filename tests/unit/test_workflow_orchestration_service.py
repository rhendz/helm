from helm_orchestration import (
    ApprovalAction,
    ApprovalDecision,
    ApprovedSyncItem,
    CalendarSyncRequest,
    CalendarSyncResult,
    CalendarSystemAdapter,
    CalendarAgentInput,
    CalendarAgentOutput,
    ExecutionFailurePayload,
    NormalizedTaskArtifact,
    NormalizedTaskValidator,
    PreparedSpecialistInput,
    RegisteredValidator,
    RetryState,
    ScheduleBlock,
    ScheduleProposalArtifact,
    ScheduleProposalValidator,
    SyncLookupRequest,
    SyncLookupResult,
    SyncOperation,
    SyncOutcomeStatus,
    SyncRetryDisposition,
    SyncTargetSystem,
    SpecialistName,
    TaskSyncRequest,
    TaskSyncResult,
    TaskSystemAdapter,
    TaskAgentInput,
    TaskAgentOutput,
    TaskArtifact,
    ValidationOutcome,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowArtifactKind,
    WorkflowOrchestrationService,
    WorkflowResumeService,
    WorkflowSpecialistStep,
    WorkflowSummaryArtifact,
    WorkflowStepExecutionError,
)
from helm_storage.db import Base
from helm_storage.repositories import (
    SQLAlchemyWorkflowSpecialistInvocationRepository,
    WorkflowArtifactType,
    WorkflowBlockedReason,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
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


def test_approved_sync_item_schema_preserves_proposal_version_anchor() -> None:
    item = ApprovedSyncItem(
        proposal_artifact_id=12,
        proposal_version_number=3,
        target_system=SyncTargetSystem.CALENDAR_SYSTEM,
        operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
        planned_item_key="calendar:focus-block-1",
        execution_order=2,
        payload_fingerprint="sha256:abc123",
        payload={"title": "Inbox triage", "start": "2026-03-16T09:00:00Z"},
    )

    payload = item.model_dump(mode="json")

    assert payload["proposal_artifact_id"] == 12
    assert payload["proposal_version_number"] == 3
    assert payload["target_system"] == SyncTargetSystem.CALENDAR_SYSTEM.value
    assert payload["operation"] == SyncOperation.CALENDAR_BLOCK_UPSERT.value
    assert payload["planned_item_key"] == "calendar:focus-block-1"


def test_adapter_protocols_use_normalized_sync_contracts() -> None:
    class StubTaskAdapter:
        def upsert_task(self, request: TaskSyncRequest) -> TaskSyncResult:
            assert request.item.target_system is SyncTargetSystem.TASK_SYSTEM
            return TaskSyncResult(
                status=SyncOutcomeStatus.SUCCEEDED,
                retry_disposition=SyncRetryDisposition.TERMINAL,
                external_object_id="task-123",
            )

        def reconcile_task(self, request: SyncLookupRequest) -> SyncLookupResult:
            assert request.operation is SyncOperation.TASK_UPSERT
            return SyncLookupResult(found=True, external_object_id="task-123")

    class StubCalendarAdapter:
        def upsert_calendar_block(self, request: CalendarSyncRequest) -> CalendarSyncResult:
            assert request.item.target_system is SyncTargetSystem.CALENDAR_SYSTEM
            return CalendarSyncResult(
                status=SyncOutcomeStatus.RECONCILIATION_REQUIRED,
                retry_disposition=SyncRetryDisposition.RECONCILE,
                error_summary="Provider timed out after request dispatch.",
            )

        def reconcile_calendar_block(self, request: SyncLookupRequest) -> SyncLookupResult:
            assert request.operation is SyncOperation.CALENDAR_BLOCK_UPSERT
            return SyncLookupResult(found=False, provider_state="missing")

    task_adapter: TaskSystemAdapter = StubTaskAdapter()
    calendar_adapter: CalendarSystemAdapter = StubCalendarAdapter()
    task_item = ApprovedSyncItem(
        proposal_artifact_id=4,
        proposal_version_number=2,
        target_system=SyncTargetSystem.TASK_SYSTEM,
        operation=SyncOperation.TASK_UPSERT,
        planned_item_key="task:triage-inbox",
        execution_order=1,
        payload_fingerprint="sha256:task",
        payload={"title": "Triage inbox"},
    )
    calendar_item = ApprovedSyncItem(
        proposal_artifact_id=4,
        proposal_version_number=2,
        target_system=SyncTargetSystem.CALENDAR_SYSTEM,
        operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
        planned_item_key="calendar:focus-block-1",
        execution_order=2,
        payload_fingerprint="sha256:cal",
        payload={"title": "Inbox triage"},
    )

    task_result = task_adapter.upsert_task(TaskSyncRequest(item=task_item))
    calendar_result = calendar_adapter.upsert_calendar_block(CalendarSyncRequest(item=calendar_item))
    lookup = calendar_adapter.reconcile_calendar_block(
        SyncLookupRequest(
            proposal_artifact_id=4,
            proposal_version_number=2,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="calendar:focus-block-1",
            payload_fingerprint="sha256:cal",
        )
    )

    assert task_result.external_object_id == "task-123"
    assert calendar_result.retry_disposition is SyncRetryDisposition.RECONCILE
    assert lookup.provider_state == "missing"


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
            ),
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.ARTIFACT_TYPE,
                    value=WorkflowArtifactKind.NORMALIZED_TASK.value,
                ),
                validator=NormalizedTaskValidator(),
            ),
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.ARTIFACT_TYPE,
                    value=WorkflowArtifactKind.SCHEDULE_PROPOSAL.value,
                ),
                validator=ScheduleProposalValidator(),
            ),
        ]
    )
    return WorkflowOrchestrationService(session, validator_registry=registry)


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
            constraints=tuple(request_artifact.payload["metadata"].get("constraints", [])),
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
                TaskArtifact(
                    title="Draft priorities",
                    summary="Prepare top work items for the week.",
                    priority="medium",
                    estimated_minutes=45,
                ),
            ),
            warnings=("Clarify whether Friday should remain meeting-light.",),
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


def _calendar_agent_step(*, valid_output: bool = True) -> WorkflowSpecialistStep:
    def _build_input(state) -> PreparedSpecialistInput:  # type: ignore[no-untyped-def]
        normalized_artifact = state.latest_artifacts[WorkflowArtifactType.NORMALIZED_TASK.value]
        request_artifact = state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
        revision_request_artifact = state.latest_artifacts.get(WorkflowArtifactType.REVISION_REQUEST.value)
        prior_proposal_artifact = state.latest_artifacts.get(WorkflowArtifactType.SCHEDULE_PROPOSAL.value)
        normalized = NormalizedTaskArtifact.model_validate(normalized_artifact.payload)
        request = CalendarAgentInput(
            workflow_type=state.run.workflow_type,
            run_id=state.run.id,
            step_name="dispatch_calendar_agent",
            normalized_task_artifact_id=normalized_artifact.id,
            tasks=normalized.tasks,
            scheduling_constraints=("Protect deep work mornings.", "Avoid lunch meetings."),
            source_context={"chat_id": request_artifact.payload["metadata"]["chat_id"]},
            request_text=request_artifact.payload["request_text"],
            warnings=normalized.warnings,
            revision_request_artifact_id=(
                revision_request_artifact.id if revision_request_artifact is not None else None
            ),
            revision_feedback=(
                revision_request_artifact.payload["feedback"] if revision_request_artifact is not None else None
            ),
            prior_proposal_artifact_id=prior_proposal_artifact.id if prior_proposal_artifact is not None else None,
            prior_proposal_version=(
                prior_proposal_artifact.version_number if prior_proposal_artifact is not None else None
            ),
        )
        return PreparedSpecialistInput(
            input_artifact_id=normalized_artifact.id,
            payload=request,
        )

    def _handler(payload: object) -> CalendarAgentOutput:
        request = CalendarAgentInput.model_validate(payload)
        time_blocks = (
            ScheduleBlock(
                title="Inbox triage",
                task_title=request.tasks[0].title,
                start="2026-03-16T09:00:00Z",
                end="2026-03-16T09:30:00Z",
            ),
        )
        if not valid_output:
            time_blocks = ()
        return CalendarAgentOutput(
            proposal_summary="Draft a focused weekly schedule from validated tasks."
            if valid_output
            else "",
            calendar_id="primary",
            time_blocks=time_blocks,
            proposed_changes=(
                "Create a Monday morning triage block.",
                "Reserve one review slot for drafting priorities.",
            ),
            warnings=("Calendar still needs a final conflict scan.",),
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


def test_task_agent_specialist_dispatch_persists_typed_input_and_advances() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_task_agent_step().key: _task_agent_step()},
        )

        resumed = resume_service.resume_run(created.run.id)
        invocation_repo = SQLAlchemyWorkflowSpecialistInvocationRepository(session)
        invocation = invocation_repo.list_for_run(created.run.id)[0]

        assert resumed.run.current_step_name == "dispatch_calendar_agent"
        assert resumed.run.status == WorkflowRunStatus.RUNNING.value
        assert resumed.latest_artifacts[WorkflowArtifactType.NORMALIZED_TASK.value].payload["title"] == "Weekly planning"
        assert invocation.specialist_name == SpecialistName.TASK_AGENT.value
        assert invocation.status == WorkflowStepStatus.SUCCEEDED.value
        assert invocation.output_artifact_id == resumed.latest_artifacts[WorkflowArtifactType.NORMALIZED_TASK.value].id


def test_specialist_resume_service_skips_blocked_runs_until_explicit_retry() -> None:
    with _session() as session:
        service = _service(session)
        blocked = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        runnable = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_task_agent_step().key: _task_agent_step()},
        )
        blocked_state = service.execute_specialist_step(
            blocked.run.id,
            WorkflowSpecialistStep(
                workflow_type="weekly_scheduling",
                step_name="dispatch_task_agent",
                specialist=SpecialistName.TASK_AGENT,
                input_builder=_task_agent_step().input_builder,
                handler=lambda _payload: TaskAgentOutput(title="Weekly planning", summary="", tasks=()),
                artifact_type=WorkflowArtifactKind.NORMALIZED_TASK,
                next_step_name="dispatch_calendar_agent",
            ),
        )
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_task_agent_step().key: _task_agent_step()},
        )

        initial_runnable = resume_service.list_runnable_runs()
        assert [state.run.id for state in initial_runnable] == [runnable.run.id]
        assert blocked_state.run.status == WorkflowRunStatus.BLOCKED.value

        service.retry_current_step(blocked.run.id, reason="Operator requested retry.")
        retried_runnable = resume_service.list_runnable_runs()
        assert [state.run.id for state in retried_runnable] == [blocked.run.id, runnable.run.id]


def test_calendar_agent_specialist_validation_failure_blocks_after_output() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        task_state = service.execute_specialist_step(created.run.id, _task_agent_step())
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_calendar_agent_step(valid_output=False).key: _calendar_agent_step(valid_output=False)},
        )

        blocked = resume_service.resume_run(task_state.run.id)
        invocation_repo = SQLAlchemyWorkflowSpecialistInvocationRepository(session)
        invocations = invocation_repo.list_for_run(created.run.id)

        assert blocked.run.status == WorkflowRunStatus.BLOCKED.value
        assert blocked.current_step is not None
        assert blocked.current_step.step_name == "dispatch_calendar_agent"
        assert blocked.current_step.status == WorkflowStepStatus.VALIDATION_FAILED.value
        assert blocked.latest_artifacts[WorkflowArtifactType.SCHEDULE_PROPOSAL.value].payload["proposal_summary"] == ""
        assert invocations[-1].specialist_name == SpecialistName.CALENDAR_AGENT.value
        assert invocations[-1].status == WorkflowStepStatus.VALIDATION_FAILED.value


def test_schedule_proposal_creates_approval_checkpoint_and_blocks_run() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        service.execute_specialist_step(created.run.id, _task_agent_step())
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_calendar_agent_step().key: _calendar_agent_step()},
        )

        completed = resume_service.resume_run(created.run.id)

        assert completed.run.status == WorkflowRunStatus.BLOCKED.value
        assert completed.run.blocked_reason == WorkflowBlockedReason.APPROVAL_REQUIRED.value
        assert completed.run.needs_action is True
        assert completed.run.current_step_name == "await_schedule_approval"
        assert completed.active_approval_checkpoint is not None
        assert completed.active_approval_checkpoint.resume_step_name == "apply_schedule"
        proposal = ScheduleProposalArtifact.model_validate(
            completed.latest_artifacts[WorkflowArtifactType.SCHEDULE_PROPOSAL.value].payload
        )
        assert proposal.warnings == ("Calendar still needs a final conflict scan.",)
        validation = completed.latest_artifacts[WorkflowArtifactType.VALIDATION_RESULT.value].payload
        assert validation["outcome"] == ValidationOutcome.PASSED_WITH_WARNINGS.value
        approval_request = completed.latest_artifacts[WorkflowArtifactType.APPROVAL_REQUEST.value].payload
        assert approval_request["allowed_actions"] == ["approve", "reject", "request_revision"]


def test_specialist_resume_service_is_restart_safe_between_task_agent_and_calendar_agent() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        first_resume = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_task_agent_step().key: _task_agent_step()},
        )
        second_resume = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_calendar_agent_step().key: _calendar_agent_step()},
        )

        after_task = first_resume.resume_run(created.run.id)
        after_task_step_name = after_task.current_step.step_name if after_task.current_step is not None else None
        after_calendar = second_resume.resume_run(created.run.id)
        invocation_repo = SQLAlchemyWorkflowSpecialistInvocationRepository(session)

        assert after_task_step_name == "dispatch_calendar_agent"
        assert after_calendar.run.status == WorkflowRunStatus.BLOCKED.value
        assert after_calendar.run.current_step_name == "await_schedule_approval"
        assert [record.specialist_name for record in invocation_repo.list_for_run(created.run.id)] == [
            SpecialistName.TASK_AGENT.value,
            SpecialistName.CALENDAR_AGENT.value,
        ]


def test_approval_decision_approve_resumes_next_persisted_step() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        service.execute_specialist_step(created.run.id, _task_agent_step())
        blocked = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_calendar_agent_step().key: _calendar_agent_step()},
        ).resume_run(created.run.id)
        target_artifact_id = blocked.active_approval_checkpoint.target_artifact_id  # type: ignore[union-attr]

        resumed = service.submit_approval_decision(
            blocked.run.id,
            decision=ApprovalDecision(
                action=ApprovalAction.APPROVE,
                actor="telegram:1",
                target_artifact_id=target_artifact_id,
            ),
        )

        assert resumed.run.status == WorkflowRunStatus.PENDING.value
        assert resumed.run.needs_action is False
        assert resumed.run.current_step_name == "apply_schedule"
        assert resumed.active_approval_checkpoint is None
        assert resumed.latest_artifacts[WorkflowArtifactType.APPROVAL_DECISION.value].payload["decision"] == (
            ApprovalAction.APPROVE.value
        )


def test_approval_decision_reject_closes_run_cleanly() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        service.execute_specialist_step(created.run.id, _task_agent_step())
        blocked = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_calendar_agent_step().key: _calendar_agent_step()},
        ).resume_run(created.run.id)
        target_artifact_id = blocked.active_approval_checkpoint.target_artifact_id  # type: ignore[union-attr]

        terminated = service.submit_approval_decision(
            blocked.run.id,
            decision=ApprovalDecision(
                action=ApprovalAction.REJECT,
                actor="telegram:1",
                target_artifact_id=target_artifact_id,
            ),
        )

        assert terminated.run.status == WorkflowRunStatus.TERMINATED.value
        assert terminated.run.needs_action is False
        assert terminated.latest_artifacts[WorkflowArtifactType.APPROVAL_DECISION.value].payload["decision"] == (
            ApprovalAction.REJECT.value
        )


def test_approval_decision_request_revision_returns_to_proposal_step() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        service.execute_specialist_step(created.run.id, _task_agent_step())
        blocked = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_calendar_agent_step().key: _calendar_agent_step()},
        ).resume_run(created.run.id)
        target_artifact_id = blocked.active_approval_checkpoint.target_artifact_id  # type: ignore[union-attr]

        revised = service.submit_approval_decision(
            blocked.run.id,
            decision=ApprovalDecision(
                action=ApprovalAction.REQUEST_REVISION,
                actor="telegram:1",
                target_artifact_id=target_artifact_id,
                revision_feedback="Keep Friday afternoon open.",
            ),
        )

        assert revised.run.status == WorkflowRunStatus.PENDING.value
        assert revised.run.current_step_name == "dispatch_calendar_agent"
        assert revised.run.current_step_attempt == 2
        assert revised.latest_artifacts[WorkflowArtifactType.REVISION_REQUEST.value].payload["feedback"] == (
            "Keep Friday afternoon open."
        )


def test_revision_request_creates_new_schedule_proposal_version_with_lineage() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        service.execute_specialist_step(created.run.id, _task_agent_step())
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={_calendar_agent_step().key: _calendar_agent_step()},
        )
        blocked = resume_service.resume_run(created.run.id)
        original_proposal = blocked.latest_artifacts[WorkflowArtifactType.SCHEDULE_PROPOSAL.value]
        revised = service.submit_approval_decision(
            blocked.run.id,
            decision=ApprovalDecision(
                action=ApprovalAction.REQUEST_REVISION,
                actor="telegram:1",
                target_artifact_id=original_proposal.id,
                revision_feedback="Keep Friday afternoon open.",
            ),
        )

        reblocked = resume_service.resume_run(revised.run.id)
        latest_proposal = reblocked.latest_artifacts[WorkflowArtifactType.SCHEDULE_PROPOSAL.value]
        revision_request = reblocked.latest_artifacts[WorkflowArtifactType.REVISION_REQUEST.value]

        assert latest_proposal.id != original_proposal.id
        assert latest_proposal.version_number == original_proposal.version_number + 1
        assert latest_proposal.supersedes_artifact_id == original_proposal.id
        assert latest_proposal.lineage_parent_id == revision_request.id
        assert revision_request.payload["target_artifact_id"] == original_proposal.id


def test_specialist_resume_service_records_handler_exceptions_as_failed_runs() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        failing_step = WorkflowSpecialistStep(
            workflow_type="weekly_scheduling",
            step_name="dispatch_task_agent",
            specialist=SpecialistName.TASK_AGENT,
            input_builder=_task_agent_step().input_builder,
            handler=lambda _payload: (_ for _ in ()).throw(
                WorkflowStepExecutionError(
                    ExecutionFailurePayload(
                        error_type="specialist_timeout",
                        message="Task agent timed out.",
                        retry_state=RetryState.RETRYABLE,
                        retryable=True,
                    )
                )
            ),
            artifact_type=WorkflowArtifactKind.NORMALIZED_TASK,
            next_step_name="dispatch_calendar_agent",
        )
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={failing_step.key: failing_step},
        )

        failed = resume_service.resume_run(created.run.id)

        assert failed.run.status == WorkflowRunStatus.FAILED.value
        assert failed.current_step is not None
        assert failed.current_step.status == WorkflowStepStatus.FAILED.value


def test_specialist_resume_service_uses_workflow_semantic_keys() -> None:
    with _session() as session:
        service = _service(session)
        created = service.create_run(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_payload=_request_payload(),
        )
        resume_service = WorkflowResumeService(
            session,
            workflow_service=service,
            specialist_steps={("other_workflow", "dispatch_task_agent"): _task_agent_step()},
        )

        failed = resume_service.resume_run(created.run.id)

        assert failed.run.status == WorkflowRunStatus.FAILED.value
        assert failed.run.failure_class == "missing_step_handler"


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
