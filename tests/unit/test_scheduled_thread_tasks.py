from datetime import UTC, datetime, timedelta

from email_agent.scheduling import run_due_scheduled_thread_tasks
from helm_runtime.email_agent import build_email_agent_runtime
from helm_storage.db import Base
from helm_storage.models import AgentRunORM
from helm_storage.repositories.agent_runs import AgentRunStatus
from helm_storage.repositories.contracts import NewEmailThread, NewScheduledThreadTask
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_storage.repositories.scheduled_thread_tasks import SQLAlchemyScheduledThreadTaskRepository
from sqlalchemy import create_engine, select
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

    result = run_due_scheduled_thread_tasks(runtime=build_email_agent_runtime(session_local))
    assert result.processed_count == 2
    assert result.skipped_count == 0
    assert result.failed_count == 0

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

    with Session(engine) as session:
        agent_runs = list(session.execute(select(AgentRunORM)).scalars().all())

    assert len(agent_runs) == 2
    assert all(run.status == AgentRunStatus.SUCCEEDED.value for run in agent_runs)


def test_due_scheduled_task_failures_are_recorded_without_stopping_batch() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        task_repo = SQLAlchemyScheduledThreadTaskRepository(session)
        failing_thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-failing-followup",
                business_state="waiting_on_other_party",
                visible_labels=(),
                current_summary="Waiting on response",
                latest_confidence_band="High",
            )
        )
        healthy_thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-healthy-reminder",
                business_state="waiting_on_user",
                visible_labels=(),
                current_summary="Need to send docs",
                latest_confidence_band="Medium",
            )
        )
        failing_thread_id = failing_thread.id
        healthy_thread_id = healthy_thread.id
        task_repo.create(
            NewScheduledThreadTask(
                email_thread_id=failing_thread_id,
                task_type="followup",
                created_by="system",
                due_at=datetime.now(UTC) - timedelta(minutes=5),
                reason="followup_due",
            )
        )
        task_repo.create(
            NewScheduledThreadTask(
                email_thread_id=healthy_thread_id,
                task_type="reminder",
                created_by="user",
                due_at=datetime.now(UTC) - timedelta(minutes=5),
                reason="reminder_due",
            )
        )

    original_update_thread_state = runtime.update_thread_state

    def _failing_update_thread_state(thread_id: int, **kwargs):  # noqa: ANN001
        if thread_id == failing_thread_id:
            raise RuntimeError("thread update failed")
        return original_update_thread_state(thread_id, **kwargs)

    runtime.update_thread_state = _failing_update_thread_state  # type: ignore[method-assign]

    result = run_due_scheduled_thread_tasks(runtime=runtime)

    assert result.processed_count == 1
    assert result.skipped_count == 0
    assert result.failed_count == 1

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        task_repo = SQLAlchemyScheduledThreadTaskRepository(session)
        failed_thread = thread_repo.get_by_provider_thread_id("thr-failing-followup")
        healthy = thread_repo.get_by_provider_thread_id("thr-healthy-reminder")
        remaining_due = task_repo.list_due(due_before=datetime.now(UTC))
        agent_runs = list(session.execute(select(AgentRunORM)).scalars().all())

    assert failed_thread is not None
    assert failed_thread.business_state == "waiting_on_other_party"
    assert failed_thread.resurfacing_source is None

    assert healthy is not None
    assert healthy.business_state == "waiting_on_user"
    assert healthy.resurfacing_source == "reminder_due"

    assert len(remaining_due) == 1
    assert remaining_due[0].email_thread_id == failing_thread_id

    statuses = sorted(run.status for run in agent_runs)
    assert statuses == [AgentRunStatus.FAILED.value, AgentRunStatus.SUCCEEDED.value]
