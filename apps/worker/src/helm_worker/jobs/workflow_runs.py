from __future__ import annotations

from datetime import UTC, datetime, timedelta

from helm_connectors import StubCalendarSystemAdapter, StubTaskSystemAdapter
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
    TaskAgentInput,
    TaskAgentOutput,
    TaskArtifact,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WeeklySchedulingRequest,
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
            task_system_adapter=StubTaskSystemAdapter(),
            calendar_system_adapter=StubCalendarSystemAdapter(),
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
        next_step_name="apply_schedule",
    )
    return {task_step.key: task_step, calendar_step.key: calendar_step}


def _build_task_agent_input(state: WorkflowRunState) -> PreparedSpecialistInput:
    request_artifact = state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
    metadata = request_artifact.payload["metadata"]
    weekly_request_payload = metadata.get("weekly_request")
    if isinstance(weekly_request_payload, dict):
        weekly_request = WeeklySchedulingRequest.model_validate(weekly_request_payload)
    else:
        weekly_request = WeeklySchedulingRequest(
            raw_request_text=request_artifact.payload["request_text"]
        )
    payload = TaskAgentInput(
        workflow_type=state.run.workflow_type,
        run_id=state.run.id,
        step_name="dispatch_task_agent",
        request_artifact_id=request_artifact.id,
        request_text=request_artifact.payload["request_text"],
        submitted_by=request_artifact.payload["submitted_by"],
        channel=request_artifact.payload["channel"],
        metadata=metadata,
        constraints=tuple(weekly_request.protected_time + weekly_request.no_meeting_windows),
        weekly_request=weekly_request,
    )
    return PreparedSpecialistInput(input_artifact_id=request_artifact.id, payload=payload)


def _run_task_agent(payload: object) -> TaskAgentOutput:
    request = TaskAgentInput.model_validate(payload)
    weekly_request = request.weekly_request or WeeklySchedulingRequest(
        raw_request_text=request.request_text
    )
    tasks = []
    warnings = list(weekly_request.warnings)
    assumptions = list(weekly_request.assumptions)
    for item in weekly_request.tasks:
        task_warnings = list(item.warnings)
        if item.priority is None:
            task_warnings.append("Priority omitted; defaulted to medium for scheduling.")
        tasks.append(
            TaskArtifact(
                title=item.title,
                summary=item.details or f"Advance {item.title}.",
                priority=item.priority or "medium",
                estimated_minutes=item.estimated_minutes or 60,
                deadline=item.deadline,
                source_line=item.source_line,
                warnings=tuple(dict.fromkeys(task_warnings)),
            )
        )
    if not tasks:
        assumptions.append(
            "Weekly request did not yield structured tasks; proposal will stay high level."
        )
    return TaskAgentOutput(
        title="Weekly scheduling request",
        summary=f"Normalize weekly brief from {request.channel} into durable task artifacts.",
        request_summary=weekly_request.planning_goal or weekly_request.raw_request_text,
        tasks=tuple(tasks),
        protected_time=weekly_request.protected_time,
        no_meeting_windows=weekly_request.no_meeting_windows,
        assumptions=tuple(dict.fromkeys(assumptions)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _build_calendar_agent_input(state: WorkflowRunState) -> PreparedSpecialistInput:
    normalized_artifact = state.latest_artifacts[WorkflowArtifactType.NORMALIZED_TASK.value]
    request_artifact = state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
    revision_request_artifact = state.latest_artifacts.get(
        WorkflowArtifactType.REVISION_REQUEST.value
    )
    prior_proposal_artifact = state.latest_artifacts.get(
        WorkflowArtifactType.SCHEDULE_PROPOSAL.value
    )
    normalized = TaskAgentOutput.model_validate(normalized_artifact.payload)
    weekly_request_payload = request_artifact.payload["metadata"].get("weekly_request")
    if isinstance(weekly_request_payload, dict):
        weekly_request = WeeklySchedulingRequest.model_validate(weekly_request_payload)
    else:
        weekly_request = WeeklySchedulingRequest(
            raw_request_text=request_artifact.payload["request_text"]
        )
    payload = CalendarAgentInput(
        workflow_type=state.run.workflow_type,
        run_id=state.run.id,
        step_name="dispatch_calendar_agent",
        normalized_task_artifact_id=normalized_artifact.id,
        tasks=normalized.tasks,
        scheduling_constraints=tuple(normalized.protected_time + normalized.no_meeting_windows),
        source_context=request_artifact.payload["metadata"],
        request_text=request_artifact.payload["request_text"],
        weekly_request=weekly_request,
        warnings=normalized.warnings,
        revision_request_artifact_id=revision_request_artifact.id
        if revision_request_artifact is not None
        else None,
        revision_feedback=(
            revision_request_artifact.payload["feedback"]
            if revision_request_artifact is not None
            else None
        ),
        prior_proposal_artifact_id=prior_proposal_artifact.id
        if prior_proposal_artifact is not None
        else None,
        prior_proposal_version=(
            prior_proposal_artifact.version_number if prior_proposal_artifact is not None else None
        ),
    )
    return PreparedSpecialistInput(input_artifact_id=normalized_artifact.id, payload=payload)


def _run_calendar_agent(payload: object) -> CalendarAgentOutput:
    request = CalendarAgentInput.model_validate(payload)
    slots = _candidate_slots(request)
    scheduled_blocks: list[ScheduleBlock] = []
    carry_forward: list[str] = []
    proposed_changes: list[str] = []
    rationale: list[str] = []
    assumptions = list(request.warnings)
    if request.revision_feedback:
        assumptions.append(f"Revision focus: {request.revision_feedback}")

    tasks = list(request.tasks)
    tasks.sort(
        key=lambda task: (
            _priority_rank(task.priority),
            task.deadline or "zzzz",
            task.title.lower(),
        )
    )
    for task, slot in zip(tasks, slots, strict=False):
        end_time = slot + timedelta(minutes=task.estimated_minutes or 60)
        scheduled_blocks.append(
            ScheduleBlock(
                title=task.title,
                task_title=task.title,
                start=slot.isoformat().replace("+00:00", "Z"),
                end=end_time.isoformat().replace("+00:00", "Z"),
            )
        )
        change = f"Schedule {task.title} on {_human_day(slot)}."
        if task.deadline:
            change += f" Deadline tracked: {task.deadline}."
        proposed_changes.append(change)

    if len(tasks) > len(scheduled_blocks):
        for task in tasks[len(scheduled_blocks) :]:
            carry_forward.append(task.title)

    if request.scheduling_constraints:
        rationale.append("Protected focus windows were filled before open review slots.")
    if any(task.deadline for task in tasks):
        rationale.append("Tasks with explicit deadlines were ordered before flexible work.")
    if request.revision_feedback:
        rationale.append(
            "Revision feedback was applied while preserving the same workflow run and proposal lineage."
        )

    honored_constraints = list(request.scheduling_constraints)
    if carry_forward:
        assumptions.append(
            "Not every task fit into the first-pass week; carry-forward work stays explicit."
        )

    summary = (
        f"Schedule {len(scheduled_blocks)} task blocks"
        f" with {len(carry_forward)} carry-forward item(s) held out of the week."
    )
    return CalendarAgentOutput(
        proposal_summary=summary,
        calendar_id="primary",
        time_blocks=tuple(scheduled_blocks),
        proposed_changes=tuple(proposed_changes),
        honored_constraints=tuple(dict.fromkeys(honored_constraints)),
        assumptions=tuple(dict.fromkeys(assumptions)),
        carry_forward_tasks=tuple(carry_forward),
        rationale=tuple(dict.fromkeys(rationale)),
        warnings=("Final conflict scan still requires operator review.",),
    )


def _candidate_slots(request: CalendarAgentInput) -> list[datetime]:
    base = datetime(2026, 3, 16, 9, tzinfo=UTC)
    protected = request.weekly_request.protected_time if request.weekly_request is not None else ()
    if protected:
        return [base + timedelta(days=index) for index in range(4)]
    return [base + timedelta(days=index, hours=(index % 2)) for index in range(5)]


def _priority_rank(priority: str | None) -> int:
    order = {"high": 0, "medium": 1, "low": 2, None: 1}
    return order.get(priority, 1)


def _human_day(value: datetime) -> str:
    return value.strftime("%A %H:%M UTC")
