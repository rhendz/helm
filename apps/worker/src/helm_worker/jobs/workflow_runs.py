from __future__ import annotations

from collections.abc import Callable

from helm_observability.logging import get_logger
from helm_orchestration import (
    NormalizedTaskValidator,
    RegisteredValidator,
    StepExecutionResult,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowArtifactKind,
    WorkflowOrchestrationService,
    WorkflowResumeService,
)
from helm_storage.db import SessionLocal
from helm_storage.repositories import WorkflowRunState
from sqlalchemy.orm import Session

StepHandler = Callable[[WorkflowRunState], StepExecutionResult]

logger = get_logger("helm_worker.jobs.workflow_runs")
STEP_HANDLERS: dict[str, StepHandler] = {}


def run(*, handlers: dict[str, StepHandler] | None = None) -> int:
    configured_handlers = dict(STEP_HANDLERS if handlers is None else handlers)
    if not configured_handlers:
        logger.info("workflow_runs_job_skipped_no_handlers")
        return 0

    with SessionLocal() as session:
        resume_service = _build_resume_service(session, handlers=configured_handlers)
        resumed = resume_service.resume_runnable_runs()
        logger.info("workflow_runs_job_processed", resumed_count=len(resumed))
        return len(resumed)


def _build_validator_registry() -> ValidatorRegistry:
    validator = NormalizedTaskValidator()
    return ValidatorRegistry(
        [
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.STEP_NAME,
                    value="normalize_request",
                ),
                validator=validator,
            ),
            RegisteredValidator(
                target=ValidatorTarget(
                    kind=ValidationTargetKind.ARTIFACT_TYPE,
                    value=WorkflowArtifactKind.NORMALIZED_TASK.value,
                ),
                validator=validator,
            ),
        ]
    )


def _build_resume_service(
    session: Session,
    *,
    handlers: dict[str, StepHandler],
) -> WorkflowResumeService:
    return WorkflowResumeService(
        session,
        workflow_service=WorkflowOrchestrationService(
            session,
            validator_registry=_build_validator_registry(),
        ),
        handlers=handlers,
    )
