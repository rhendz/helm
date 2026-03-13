from __future__ import annotations

from helm_observability.logging import get_logger
from helm_orchestration import (
    NormalizedTaskValidator,
    RegisteredValidator,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowArtifactKind,
    WorkflowOrchestrationService,
    WorkflowResumeService,
)
from helm_storage.db import SessionLocal

logger = get_logger("helm_worker.jobs.workflow_runs")


def run() -> None:
    with SessionLocal() as session:
        resume_service = WorkflowResumeService(
            session,
            workflow_service=WorkflowOrchestrationService(
                session,
                validator_registry=_build_validator_registry(),
            ),
            handlers={},
        )
        resumed = resume_service.resume_runnable_runs()
        logger.info("workflow_runs_job_processed", resumed_count=len(resumed))


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
