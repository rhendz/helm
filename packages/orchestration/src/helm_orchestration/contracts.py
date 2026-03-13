from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from helm_orchestration.schemas import ExecutionFailurePayload, ValidationReport
from helm_storage.repositories import WorkflowRunState


class WorkflowArtifactKind(StrEnum):
    RAW_REQUEST = "raw_request"
    NORMALIZED_TASK = "normalized_task"
    SCHEDULE_PROPOSAL = "schedule_proposal"
    VALIDATION_RESULT = "validation_result"
    FINAL_SUMMARY = "final_summary"


class SpecialistName(StrEnum):
    TASK_AGENT = "task_agent"
    CALENDAR_AGENT = "calendar_agent"


class ValidationTargetKind(StrEnum):
    STEP_NAME = "step_name"
    ARTIFACT_TYPE = "artifact_type"


@dataclass(frozen=True, slots=True)
class ValidatorTarget:
    kind: ValidationTargetKind
    value: str


class WorkflowValidator(Protocol):
    name: str

    def validate(self, payload: object) -> ValidationReport: ...


@dataclass(frozen=True, slots=True)
class RegisteredValidator:
    target: ValidatorTarget
    validator: WorkflowValidator


@dataclass(frozen=True, slots=True)
class PreparedSpecialistInput:
    input_artifact_id: int
    payload: object


class SpecialistInputBuilder(Protocol):
    def __call__(self, state: WorkflowRunState) -> PreparedSpecialistInput: ...


class SpecialistHandler(Protocol):
    def __call__(self, payload: object) -> object: ...


@dataclass(frozen=True, slots=True)
class WorkflowSpecialistStep:
    workflow_type: str
    step_name: str
    specialist: SpecialistName
    input_builder: SpecialistInputBuilder
    handler: SpecialistHandler
    artifact_type: WorkflowArtifactKind
    next_step_name: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.workflow_type, self.step_name)


class WorkflowStepExecutionError(RuntimeError):
    def __init__(self, failure: ExecutionFailurePayload) -> None:
        super().__init__(failure.message)
        self.failure = failure
