from helm_storage.db import Base
from helm_storage.models import WorkflowArtifactORM, WorkflowEventORM, WorkflowRunORM, WorkflowStepORM
from sqlalchemy import create_engine, inspect


def test_workflow_schema_tables_exist_in_metadata() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)

    assert set(inspector.get_table_names()) >= {
        "workflow_runs",
        "workflow_steps",
        "workflow_artifacts",
        "workflow_events",
    }

    run_columns = {column["name"] for column in inspector.get_columns("workflow_runs")}
    assert {"status", "current_step_name", "needs_action", "validation_outcome_summary"} <= run_columns

    step_columns = {column["name"] for column in inspector.get_columns("workflow_steps")}
    assert {"step_name", "attempt_number", "failure_class", "retry_state"} <= step_columns

    artifact_columns = {column["name"] for column in inspector.get_columns("workflow_artifacts")}
    assert {
        "artifact_type",
        "schema_version",
        "version_number",
        "lineage_parent_id",
        "supersedes_artifact_id",
        "payload",
    } <= artifact_columns

    event_columns = {column["name"] for column in inspector.get_columns("workflow_events")}
    assert {"event_type", "run_status", "step_status", "details"} <= event_columns

    assert WorkflowRunORM.__tablename__ == "workflow_runs"
    assert WorkflowStepORM.__tablename__ == "workflow_steps"
    assert WorkflowArtifactORM.__tablename__ == "workflow_artifacts"
    assert WorkflowEventORM.__tablename__ == "workflow_events"
