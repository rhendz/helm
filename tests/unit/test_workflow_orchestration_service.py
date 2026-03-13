from helm_orchestration import (
    NormalizedTaskArtifact,
    NormalizedTaskValidator,
    RegisteredValidator,
    TaskArtifact,
    ValidationOutcome,
    ValidationTargetKind,
    ValidatorRegistry,
    ValidatorTarget,
    WorkflowArtifactKind,
    WorkflowSummaryArtifact,
)


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
