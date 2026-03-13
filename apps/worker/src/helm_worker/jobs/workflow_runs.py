from __future__ import annotations

from helm_observability.logging import get_logger
from helm_orchestration import (
    CalendarAgentInput,
    CalendarAgentOutput,
    NormalizedTaskValidator,
    PreparedSpecialistInput,
    RegisteredValidator,
    ScheduleBlock,
    ScheduleProposalValidator,
    SpecialistName,
    TaskArtifact,
    TaskAgentInput,
    TaskAgentOutput,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowArtifactKind,
    WorkflowOrchestrationService,
    WorkflowResumeService,
    WorkflowSpecialistStep,
)
from helm_storage.db import SessionLocal
from helm_storage.repositories import WorkflowArtifactType, WorkflowRunState
from sqlalchemy.orm import Session

logger = get_logger("helm_worker.jobs.workflow_runs")
STEP_HANDLERS: dict[tuple[str, str], WorkflowSpecialistStep] = {}


def run(*, handlers: dict[tuple[str, str], WorkflowSpecialistStep] | None = None) -> int:
    default_handlers = _build_specialist_steps()
    configured_handlers = dict(STEP_HANDLERS if handlers is None else handlers)
    if not configured_handlers:
        configured_handlers = default_handlers
    if not configured_handlers:
        logger.info("workflow_runs_job_skipped_no_handlers")
        return 0

    with SessionLocal() as session:
        resume_service = _build_resume_service(session, handlers=configured_handlers)
        resumed = resume_service.resume_runnable_runs()
        logger.info("workflow_runs_job_processed", resumed_count=len(resumed))
        return len(resumed)


def _build_validator_registry() -> ValidatorRegistry:
    task_validator = NormalizedTaskValidator()
    schedule_validator = ScheduleProposalValidator()
    return ValidatorRegistry(
        [
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.STEP_NAME,
                    value="normalize_request",
                ),
                validator=task_validator,
            ),
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.ARTIFACT_TYPE,
                    value=WorkflowArtifactKind.NORMALIZED_TASK.value,
                ),
                validator=task_validator,
            ),
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.ARTIFACT_TYPE,
                    value=WorkflowArtifactKind.SCHEDULE_PROPOSAL.value,
                ),
                validator=schedule_validator,
            ),
        ]
    )


def _build_resume_service(
    session: Session,
    *,
    handlers: dict[tuple[str, str], WorkflowSpecialistStep],
) -> WorkflowResumeService:
    return WorkflowResumeService(
        session,
        workflow_service=WorkflowOrchestrationService(
            session,
            validator_registry=_build_validator_registry(),
        ),
        specialist_steps=handlers,
    )


def _build_specialist_steps() -> dict[tuple[str, str], WorkflowSpecialistStep]:
    task_step = WorkflowSpecialistStep(
        workflow_type="weekly_scheduling",
        step_name="dispatch_task_agent",
        specialist=SpecialistName.TASK_AGENT,
        input_builder=_build_task_agent_input,
        handler=_run_task_agent,
        artifact_type=WorkflowArtifactKind.NORMALIZED_TASK,
        next_step_name="dispatch_calendar_agent",
    )
    calendar_step = WorkflowSpecialistStep(
        workflow_type="weekly_scheduling",
        step_name="dispatch_calendar_agent",
        specialist=SpecialistName.CALENDAR_AGENT,
        input_builder=_build_calendar_agent_input,
        handler=_run_calendar_agent,
        artifact_type=WorkflowArtifactKind.SCHEDULE_PROPOSAL,
        next_step_name=None,
    )
    return {task_step.key: task_step, calendar_step.key: calendar_step}


def _build_task_agent_input(state: WorkflowRunState) -> PreparedSpecialistInput:
    request_artifact = state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
    metadata = request_artifact.payload["metadata"]
    payload = TaskAgentInput(
        workflow_type=state.run.workflow_type,
        run_id=state.run.id,
        step_name="dispatch_task_agent",
        request_artifact_id=request_artifact.id,
        request_text=request_artifact.payload["request_text"],
        submitted_by=request_artifact.payload["submitted_by"],
        channel=request_artifact.payload["channel"],
        metadata=metadata,
        constraints=tuple(metadata.get("constraints", ())),
    )
    return PreparedSpecialistInput(input_artifact_id=request_artifact.id, payload=payload)


def _run_task_agent(payload: object) -> TaskAgentOutput:
    request = TaskAgentInput.model_validate(payload)
    return TaskAgentOutput(
        title="Weekly scheduling request",
        summary=f"Normalize request from {request.channel}: {request.request_text}",
        tasks=(
            TaskArtifact(
                title="Triage inbox",
                summary="Clear pending email and identify follow-ups.",
                priority="high",
                estimated_minutes=30,
            ),
            TaskArtifact(
                title="Plan top priorities",
                summary="Choose the highest-leverage work for the week.",
                priority="medium",
                estimated_minutes=45,
            ),
        ),
        warnings=("Assumes Friday afternoon remains flexible.",),
    )


def _build_calendar_agent_input(state: WorkflowRunState) -> PreparedSpecialistInput:
    normalized_artifact = state.latest_artifacts[WorkflowArtifactType.NORMALIZED_TASK.value]
    request_artifact = state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
    normalized = TaskAgentOutput.model_validate(normalized_artifact.payload)
    payload = CalendarAgentInput(
        workflow_type=state.run.workflow_type,
        run_id=state.run.id,
        step_name="dispatch_calendar_agent",
        normalized_task_artifact_id=normalized_artifact.id,
        tasks=normalized.tasks,
        scheduling_constraints=("Protect deep work mornings.", "Avoid lunch meetings."),
        source_context=request_artifact.payload["metadata"],
        request_text=request_artifact.payload["request_text"],
        warnings=normalized.warnings,
    )
    return PreparedSpecialistInput(input_artifact_id=normalized_artifact.id, payload=payload)


def _run_calendar_agent(payload: object) -> CalendarAgentOutput:
    request = CalendarAgentInput.model_validate(payload)
    first_task = request.tasks[0]
    return CalendarAgentOutput(
        proposal_summary="Convert normalized tasks into a lightweight weekly schedule proposal.",
        calendar_id="primary",
        time_blocks=(
            ScheduleBlock(
                title="Inbox triage",
                task_title=first_task.title,
                start="2026-03-16T09:00:00Z",
                end="2026-03-16T09:30:00Z",
            ),
            ScheduleBlock(
                title="Priority planning",
                task_title=request.tasks[1].title if len(request.tasks) > 1 else first_task.title,
                start="2026-03-17T10:00:00Z",
                end="2026-03-17T10:45:00Z",
            ),
        ),
        proposed_changes=(
            "Create a Monday inbox triage block.",
            "Reserve Tuesday morning for weekly planning.",
        ),
        warnings=("Final conflict scan still requires operator review.",),
    )
