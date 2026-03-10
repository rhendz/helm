from datetime import UTC, datetime, timedelta

from email_agent.adapters import build_helm_runtime
from email_agent.scheduling import run_due_scheduled_thread_tasks
from helm_storage.db import Base
from helm_storage.repositories.contracts import NewEmailThread, NewScheduledThreadTask
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_storage.repositories.scheduled_thread_tasks import SQLAlchemyScheduledThreadTaskRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_due_scheduled_tasks_update_resurfacing_metadata_and_complete_tasks() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        task_repo = SQLAlchemyScheduledThreadTaskRepository(session)
        followup_thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-followup",
                business_state="waiting_on_other_party",
                visible_labels=(),
                current_summary="Waiting on recruiter",
                latest_confidence_band="High",
            )
        )
        reminder_thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-reminder",
                business_state="waiting_on_user",
                visible_labels=("Urgent",),
                current_summary="Remember to send docs",
                latest_confidence_band="Medium",
            )
        )
        task_repo.create(
            NewScheduledThreadTask(
                email_thread_id=followup_thread.id,
                task_type="followup",
                created_by="system",
                due_at=datetime.now(UTC) - timedelta(minutes=5),
                reason="followup_due",
            )
        )
        task_repo.create(
            NewScheduledThreadTask(
                email_thread_id=reminder_thread.id,
                task_type="reminder",
                created_by="user",
                due_at=datetime.now(UTC) - timedelta(minutes=5),
                reason="reminder_due",
            )
        )

    result = run_due_scheduled_thread_tasks(runtime=build_helm_runtime(session_local))
    assert result.processed_count == 2
    assert result.skipped_count == 0

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        task_repo = SQLAlchemyScheduledThreadTaskRepository(session)
        followup = thread_repo.get_by_provider_thread_id("thr-followup")
        reminder = thread_repo.get_by_provider_thread_id("thr-reminder")
        due_after_run = task_repo.list_due(due_before=datetime.now(UTC))

    assert followup is not None
    assert followup.business_state == "waiting_on_other_party"
    assert followup.resurfacing_source == "stale_followup"
    assert followup.action_reason == "followup_due"
    assert followup.visible_labels == "Action"

    assert reminder is not None
    assert reminder.business_state == "waiting_on_user"
    assert reminder.resurfacing_source == "reminder_due"
    assert reminder.action_reason == "reminder_due"
    assert reminder.visible_labels == "Action,Urgent"

    assert due_after_run == []
