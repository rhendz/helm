from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from helm_orchestration.schemas import ValidationReport


class WorkflowArtifactKind(StrEnum):
    RAW_REQUEST = "raw_request"
    NORMALIZED_TASK = "normalized_task"
    VALIDATION_RESULT = "validation_result"
    FINAL_SUMMARY = "final_summary"


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
class StepExecutionResult:
    artifact_type: WorkflowArtifactKind
    payload: object
    next_step_name: str | None = None
