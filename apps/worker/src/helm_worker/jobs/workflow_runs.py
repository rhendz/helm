from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from helm_llm.client import LLMClient
from helm_observability.logging import get_logger
from helm_orchestration import (
    CalendarAgentInput,
    CalendarAgentOutput,
    NormalizedTaskValidator,
    PastEventError,
    PreparedSpecialistInput,
    RegisteredValidator,
    ScheduleBlock,
    ScheduleProposalValidator,
    SpecialistName,
    StubTaskSystemAdapter,
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
    compute_reference_week,
    parse_local_slot,
    past_event_guard,
    to_utc,
)
from helm_providers import GoogleCalendarProvider
from helm_storage.db import SessionLocal
from helm_storage.repositories import WorkflowArtifactType, WorkflowRunState
from helm_storage.repositories.users import get_user_by_telegram_id
from helm_worker.config import settings
from sqlalchemy.orm import Session

logger = get_logger("helm_worker.jobs.workflow_runs")
STEP_HANDLERS: dict[tuple[str, str], WorkflowSpecialistStep] = {}

# Used by _parse_duration_from_title — regex lives here since it's the only consumer
_RANGE_PATTERN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*[-\u2013]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
    re.IGNORECASE,
)


def run(*, handlers: dict[tuple[str, str], WorkflowSpecialistStep] | None = None) -> int:
    default_handlers = _build_specialist_steps()
    configured_handlers = dict(STEP_HANDLERS if handlers is None else handlers)
    if not configured_handlers:
        configured_handlers = default_handlers
    if not configured_handlers:
        logger.info("workflow_runs_job_skipped_no_handlers")
        return 0

    with SessionLocal() as session:
        user_id = _resolve_bootstrap_user_id(session)
        resume_service = _build_resume_service(session, handlers=configured_handlers, user_id=user_id)
        resumed = resume_service.resume_runnable_runs()
        logger.info("workflow_runs_job_processed", resumed_count=len(resumed))

    # Fire proactive notifications for any run that reached needs_action=True
    for state in resumed:
        if not state.run.needs_action:
            continue
        try:
            from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService
            proposal_summary = ""
            schedule_proposal = state.latest_artifacts.get(
                WorkflowArtifactType.SCHEDULE_PROPOSAL.value
            )
            if schedule_proposal is not None:
                proposal_summary = schedule_proposal.payload.get("proposal_summary") or ""
            TelegramDigestDeliveryService().notify_approval_needed(
                state.run.id, proposal_summary
            )
            logger.info(
                "proactive_approval_notification_sent",
                run_id=state.run.id,
                workflow_type=state.run.workflow_type,
            )
        except Exception:
            logger.warning(
                "proactive_approval_notification_failed",
                run_id=state.run.id,
                exc_info=True,
            )

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


def _resolve_bootstrap_user_id(db: Session) -> int:
    """Look up the single bootstrap user from the TELEGRAM_ALLOWED_USER_ID env var.

    # TODO: V1 single-user workaround — in multi-user future, _run_task_inference
    # needs to know which user's credentials to use without relying on a global env var.
    """
    telegram_user_id_str = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
    if not telegram_user_id_str:
        raise RuntimeError(
            "Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set"
        )
    user = get_user_by_telegram_id(int(telegram_user_id_str), db)
    if user is None:
        raise RuntimeError(
            f"Bootstrap user not found: no user with telegram_user_id={telegram_user_id_str}"
        )
    return user.id


def _build_calendar_provider(db: Session, user_id: int) -> GoogleCalendarProvider:
    """Construct a GoogleCalendarProvider for the given user and log construction."""
    provider = GoogleCalendarProvider(user_id, db)
    logger.info("calendar_provider_constructed", user_id=user_id, source="db_credentials")
    return provider


def _build_resume_service(
    session: Session,
    *,
    handlers: dict[tuple[str, str], WorkflowSpecialistStep],
    user_id: int,
) -> WorkflowResumeService:
    return WorkflowResumeService(
        session,
        workflow_service=WorkflowOrchestrationService(
            session,
            validator_registry=_build_validator_registry(),
            task_system_adapter=StubTaskSystemAdapter(),
            calendar_system_adapter=_build_calendar_provider(db=session, user_id=user_id),
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
    task_inference_step = _build_task_quick_add_step()
    return {
        task_step.key: task_step,
        calendar_step.key: calendar_step,
        task_inference_step.key: task_inference_step,
    }


def _build_task_quick_add_step() -> WorkflowSpecialistStep:
    """Build the worker-recovery step handler for task_quick_add runs.

    This handler is invoked by the polling loop for orphaned runs where the Telegram
    handler's inline path never called complete_current_step (e.g. crash before completion).
    It performs the full inference + CalendarAgentOutput construction so the run can
    advance to the approval checkpoint.
    """
    return WorkflowSpecialistStep(
        workflow_type="task_quick_add",
        step_name="infer_task_semantics",
        specialist=SpecialistName.TASK_INFERENCE,
        input_builder=_build_task_quick_add_input,
        handler=_run_task_inference,
        artifact_type=WorkflowArtifactKind.SCHEDULE_PROPOSAL,
        next_step_name="apply_schedule",
    )


def _build_task_quick_add_input(state: WorkflowRunState) -> PreparedSpecialistInput:
    request_artifact = state.latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
    return PreparedSpecialistInput(
        input_artifact_id=request_artifact.id,
        payload=request_artifact.payload["request_text"],
    )


def _run_task_inference(payload: object) -> CalendarAgentOutput:
    """Worker recovery handler: infer semantics and build a CalendarAgentOutput."""
    request_text = str(payload)
    tz = ZoneInfo(settings.operator_timezone)
    semantics = LLMClient().infer_task_semantics(request_text)

    # Use the LLM-suggested date at 9am local time.
    # Fall back to tomorrow 9am if the LLM returned None or the date is in the past.
    now_local = datetime.now(tz)
    local_start: datetime | None = None
    if semantics.suggested_date:
        try:
            from datetime import date as _date
            suggested = _date.fromisoformat(semantics.suggested_date)
            local_start = datetime(suggested.year, suggested.month, suggested.day, 9, 0, 0, tzinfo=tz)
            if local_start <= now_local:
                local_start = None  # LLM hallucinated a past date — fall through to default
        except ValueError:
            local_start = None

    if local_start is None:
        candidate = now_local.replace(hour=9, minute=0, second=0, microsecond=0)
        if candidate <= now_local:
            candidate = candidate + timedelta(days=1)
        local_start = candidate

    start_utc = to_utc(local_start, tz)
    end_utc = start_utc + timedelta(minutes=semantics.sizing_minutes or 60)

    try:
        past_event_guard(start_utc, tz)
    except PastEventError as exc:
        logger.warning(
            "task_quick_add_past_event_guard_triggered",
            request_text=request_text,
            reason=str(exc),
        )
        raise

    block = ScheduleBlock(
        title=request_text,
        task_title=request_text,
        start=start_utc.isoformat(),
        end=end_utc.isoformat(),
    )
    return CalendarAgentOutput(
        proposal_summary=f"Schedule: {request_text}",
        calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary"),
        time_blocks=(block,),
        proposed_changes=(f"Schedule {request_text}",),
    )


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
    tz = ZoneInfo(settings.operator_timezone)

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

    slots = _candidate_slots(request, tz)
    for task, slot in zip(tasks, slots, strict=False):
        # Try to parse explicit duration from title (e.g. "10am-12pm" → 120 min)
        duration_minutes = _parse_duration_from_title(task.title) or task.estimated_minutes or 60
        # Use shared parse_local_slot to extract day/time from title; fall back to slot
        local_start = parse_local_slot(task.title, week_start=slot, tz=tz) or slot
        start_utc = to_utc(local_start, tz)
        end_utc = start_utc + timedelta(minutes=duration_minutes)

        try:
            past_event_guard(start_utc, tz)
        except PastEventError as exc:
            logger.warning(
                "past_event_guard_triggered",
                task_title=task.title,
                reason=str(exc),
            )
            carry_forward.append(task.title)
            continue

        scheduled_blocks.append(
            ScheduleBlock(
                title=task.title,
                task_title=task.title,
                start=start_utc.isoformat(),
                end=end_utc.isoformat(),
            )
        )
        change = f"Schedule {task.title} on {_human_day(start_utc)}."
        if task.deadline:
            change += f" Deadline tracked: {task.deadline}."
        proposed_changes.append(change)

    if len(tasks) > len(scheduled_blocks) + len(carry_forward):
        for task in tasks[len(scheduled_blocks) + len(carry_forward):]:
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
        calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary"),
        time_blocks=tuple(scheduled_blocks),
        proposed_changes=tuple(proposed_changes),
        honored_constraints=tuple(dict.fromkeys(honored_constraints)),
        assumptions=tuple(dict.fromkeys(assumptions)),
        carry_forward_tasks=tuple(carry_forward),
        rationale=tuple(dict.fromkeys(rationale)),
        warnings=("Final conflict scan still requires operator review.",),
    )


def _candidate_slots(request: CalendarAgentInput, tz: ZoneInfo) -> list[datetime]:
    week_monday = compute_reference_week(tz)
    protected = request.weekly_request.protected_time if request.weekly_request is not None else ()
    if protected:
        return [week_monday + timedelta(days=index, hours=9) for index in range(4)]
    return [week_monday + timedelta(days=index, hours=9 + (index % 2)) for index in range(5)]


def _parse_duration_from_title(title: str) -> int | None:
    """Parse duration in minutes from a time range in the title, e.g. '10am-12pm' → 120."""
    match = _RANGE_PATTERN.search(title)
    if not match:
        return None
    try:
        start_h = int(match.group(1))
        start_m = int(match.group(2) or 0)
        start_ampm = (match.group(3) or match.group(6) or "am").lower()
        end_h = int(match.group(4))
        end_m = int(match.group(5) or 0)
        end_ampm = match.group(6).lower()

        if start_ampm == "pm" and start_h != 12:
            start_h += 12
        elif start_ampm == "am" and start_h == 12:
            start_h = 0
        if end_ampm == "pm" and end_h != 12:
            end_h += 12
        elif end_ampm == "am" and end_h == 12:
            end_h = 0

        duration = (end_h * 60 + end_m) - (start_h * 60 + start_m)
        return duration if duration > 0 else None
    except (ValueError, AttributeError):
        return None


def _priority_rank(priority: str | None) -> int:
    order = {"high": 0, "medium": 1, "low": 2, None: 1}
    return order.get(priority, 1)


def _human_day(value: datetime) -> str:
    local = value.astimezone() if value.tzinfo else value
    return local.strftime("%A %H:%M %Z")
