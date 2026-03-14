from __future__ import annotations

from collections.abc import Iterable

from helm_orchestration.contracts import (
    RegisteredValidator,
    ValidationTargetKind,
    ValidatorTarget,
    WorkflowValidator,
)
from helm_orchestration.schemas import (
    NormalizedTaskArtifact,
    ScheduleProposalArtifact,
    ValidationIssue,
    ValidationOutcome,
    ValidationReport,
)


class ValidatorRegistry:
    def __init__(self, validators: Iterable[RegisteredValidator] | None = None) -> None:
        self._by_step_name: dict[str, WorkflowValidator] = {}
        self._by_artifact_type: dict[str, WorkflowValidator] = {}
        for item in validators or ():
            self.register(item.target, item.validator)

    def register(self, target: ValidatorTarget, validator: WorkflowValidator) -> None:
        if target.kind is ValidationTargetKind.STEP_NAME:
            self._by_step_name[target.value] = validator
            return
        self._by_artifact_type[target.value] = validator

    def get_for_step(self, step_name: str) -> WorkflowValidator | None:
        return self._by_step_name.get(step_name)

    def get_for_artifact_type(self, artifact_type: str) -> WorkflowValidator | None:
        return self._by_artifact_type.get(artifact_type)

    def validate_for_step(self, step_name: str, payload: object) -> ValidationReport:
        validator = self.get_for_step(step_name)
        if validator is None:
            return _default_report(summary=f"No validator registered for step {step_name!r}.")
        return validator.validate(payload)

    def validate_for_artifact_type(self, artifact_type: str, payload: object) -> ValidationReport:
        validator = self.get_for_artifact_type(artifact_type)
        if validator is None:
            return _default_report(
                summary=f"No validator registered for artifact {artifact_type!r}."
            )
        return validator.validate(payload)


class NormalizedTaskValidator:
    name = "normalized-task-validator"

    def validate(self, payload: object) -> ValidationReport:
        artifact = (
            payload
            if isinstance(payload, NormalizedTaskArtifact)
            else NormalizedTaskArtifact.model_validate(payload)
        )

        issues: list[ValidationIssue] = []
        warnings: list[str] = list(artifact.warnings)

        if not artifact.title.strip():
            issues.append(
                ValidationIssue(
                    code="missing_title",
                    message="Normalized task artifact requires a title.",
                    path=("title",),
                )
            )
        if not artifact.summary.strip():
            issues.append(
                ValidationIssue(
                    code="missing_summary",
                    message="Normalized task artifact requires a summary.",
                    path=("summary",),
                )
            )
        if not artifact.tasks:
            issues.append(
                ValidationIssue(
                    code="missing_tasks",
                    message="Normalized task artifact must include at least one task.",
                    path=("tasks",),
                )
            )

        for index, task in enumerate(artifact.tasks):
            if not task.title.strip():
                issues.append(
                    ValidationIssue(
                        code="task_missing_title",
                        message="Each normalized task requires a title.",
                        path=("tasks", str(index), "title"),
                    )
                )
            if task.estimated_minutes is not None and task.estimated_minutes <= 0:
                issues.append(
                    ValidationIssue(
                        code="invalid_estimate",
                        message="Estimated minutes must be greater than zero when provided.",
                        path=("tasks", str(index), "estimated_minutes"),
                    )
                )
            if task.priority is None:
                warnings.append(f"Task {index + 1} is missing a priority.")

        if issues:
            return ValidationReport(
                outcome=ValidationOutcome.FAILED,
                summary="Normalized task artifact failed validation.",
                validator_name=self.name,
                issues=tuple(issues),
                warnings=tuple(warnings),
            )
        if warnings:
            return ValidationReport(
                outcome=ValidationOutcome.PASSED_WITH_WARNINGS,
                summary="Normalized task artifact passed with warnings.",
                validator_name=self.name,
                warnings=tuple(warnings),
            )
        return ValidationReport(
            outcome=ValidationOutcome.PASSED,
            summary="Normalized task artifact passed validation.",
            validator_name=self.name,
        )


class ScheduleProposalValidator:
    name = "schedule-proposal-validator"

    def validate(self, payload: object) -> ValidationReport:
        artifact = (
            payload
            if isinstance(payload, ScheduleProposalArtifact)
            else ScheduleProposalArtifact.model_validate(payload)
        )

        issues: list[ValidationIssue] = []
        warnings: list[str] = list(artifact.warnings)

        if not artifact.proposal_summary.strip():
            issues.append(
                ValidationIssue(
                    code="missing_summary",
                    message="Schedule proposal requires a summary.",
                    path=("proposal_summary",),
                )
            )
        if not artifact.time_blocks:
            issues.append(
                ValidationIssue(
                    code="missing_time_blocks",
                    message="Schedule proposal must include at least one time block.",
                    path=("time_blocks",),
                )
            )

        for index, block in enumerate(artifact.time_blocks):
            if not block.title.strip():
                issues.append(
                    ValidationIssue(
                        code="block_missing_title",
                        message="Each schedule block requires a title.",
                        path=("time_blocks", str(index), "title"),
                    )
                )
            if not block.start.strip() or not block.end.strip():
                issues.append(
                    ValidationIssue(
                        code="block_missing_window",
                        message="Each schedule block requires start and end timestamps.",
                        path=("time_blocks", str(index)),
                    )
                )

        if issues:
            return ValidationReport(
                outcome=ValidationOutcome.FAILED,
                summary="Schedule proposal failed validation.",
                validator_name=self.name,
                issues=tuple(issues),
                warnings=tuple(warnings),
            )
        if warnings:
            return ValidationReport(
                outcome=ValidationOutcome.PASSED_WITH_WARNINGS,
                summary="Schedule proposal passed with warnings.",
                validator_name=self.name,
                warnings=tuple(warnings),
            )
        return ValidationReport(
            outcome=ValidationOutcome.PASSED,
            summary="Schedule proposal passed validation.",
            validator_name=self.name,
        )


def _default_report(*, summary: str) -> ValidationReport:
    return ValidationReport(
        outcome=ValidationOutcome.PASSED,
        summary=summary,
        validator_name="unregistered-validator",
    )
