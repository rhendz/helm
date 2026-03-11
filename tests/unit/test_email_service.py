from datetime import UTC, datetime

from email_agent import query as email_query
from email_agent.adapters import build_helm_runtime
from email_agent.operator import approve_draft
from email_agent.reminders import (
    complete_scheduled_task,
    complete_thread_task,
    create_thread_reminder,
    list_scheduled_tasks,
    list_thread_scheduled_tasks,
)
from email_agent.reprocess import reprocess_email_thread
from email_agent.types import EmailMessage
from helm_api.services.email_service import list_send_attempts, override_thread, send_draft
from helm_connectors.gmail import GmailSendError, GmailSendResult
from helm_storage.db import Base
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.contracts import NewActionProposal, NewEmailDraft, NewEmailThread
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_email_service_lists_threads_proposals_and_drafts(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)

        thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-api-1",
                business_state="waiting_on_user",
                visible_labels=("Action", "Urgent"),
                current_summary="Recruiter follow-up",
                latest_confidence_band="High",
                resurfacing_source="new_message",
                action_reason="reply_needed",
            )
        )
        proposal = proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Reply with availability",
                confidence_band="High",
            )
        )
        draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                draft_body="Thanks, I would be glad to connect.",
                draft_subject="Re: Interview availability",
            )
        )

    threads = email_query.list_email_threads(runtime=runtime)
    proposals = email_query.list_email_proposals(runtime=runtime)
    drafts = email_query.list_email_drafts(runtime=runtime)

    assert len(threads) == 1
    assert threads[0]["provider_thread_id"] == "thr-api-1"
    assert threads[0]["visible_labels"] == ["Action", "Urgent"]
    assert len(proposals) == 1
    assert proposals[0]["proposal_type"] == "reply"
    assert len(drafts) == 1
    assert drafts[0]["approval_status"] == "pending_user"


def test_email_service_filters_threads_by_state_and_label() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-review",
                business_state="needs_review",
                visible_labels=("NeedsReview",),
            )
        )
        thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-waiting",
                business_state="waiting_on_user",
                visible_labels=("Action",),
            )
        )

    review_threads = email_query.list_email_threads(
        runtime=runtime,
        business_state="needs_review",
    )
    action_threads = email_query.list_email_threads(
        runtime=runtime,
        label="Action",
    )

    assert len(review_threads) == 1
    assert review_threads[0]["provider_thread_id"] == "thr-review"
    assert len(action_threads) == 1


def test_email_service_filters_proposals_and_drafts() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)
        thread = thread_repo.create(NewEmailThread(provider_thread_id="thr-filter-1"))

        proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Reply now",
                status="proposed",
            )
        )
        proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="review",
                rationale="Need manual review",
                status="dismissed",
            )
        )
        draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Pending approval",
                approval_status="pending_user",
            )
        )
        draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Already approved",
                approval_status="approved",
            )
        )

    filtered_proposals = email_query.list_email_proposals(
        runtime=runtime,
        status="proposed",
        proposal_type="reply",
    )
    filtered_drafts = email_query.list_email_drafts(
        runtime=runtime,
        approval_status="approved",
    )

    assert len(filtered_proposals) == 1
    assert filtered_proposals[0]["proposal_type"] == "reply"
    assert filtered_proposals[0]["status"] == "proposed"
    assert len(filtered_drafts) == 1
    assert filtered_drafts[0]["approval_status"] == "approved"


def test_email_thread_detail_and_reprocess() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)
        message_repo = SQLAlchemyEmailMessageRepository(session)

        thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-api-detail",
                business_state="waiting_on_user",
                visible_labels=("Action",),
                current_summary="Need to reply",
            )
        )
        thread_id = thread.id
        proposal = proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread_id,
                proposal_type="reply",
                rationale="Reply to recruiter",
                confidence_band="High",
            )
        )
        draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread_id,
                action_proposal_id=proposal.id,
                draft_body="Thanks for reaching out.",
                draft_subject="Re: Opportunity",
            )
        )
        message_repo.upsert_from_normalized(
            EmailMessage(
                provider_message_id="msg-api-detail",
                provider_thread_id="thr-api-detail",
                from_address="recruiter@example.com",
                subject="Opportunity",
                body_text="Can we schedule time?",
                received_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
                normalized_at=datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC),
                source="gmail",
            ),
            email_thread_id=thread_id,
        )

    detail = email_query.get_email_thread_detail(thread_id=thread_id, runtime=runtime)
    assert detail is not None
    assert detail["thread"]["provider_thread_id"] == "thr-api-detail"
    assert len(detail["proposals"]) == 1
    assert len(detail["drafts"]) == 1
    assert len(detail["messages"]) == 1

    dry_run = reprocess_email_thread(thread_id=thread_id, dry_run=True, runtime=runtime)
    assert dry_run.status == "accepted"
    assert dry_run.reprocessed is False

    executed = reprocess_email_thread(thread_id=thread_id, dry_run=False, runtime=runtime)
    assert executed.status == "accepted"
    assert executed.reprocessed is True
    assert executed.workflow_status == "completed"

    detail = email_query.get_email_thread_detail(thread_id=thread_id, runtime=runtime)
    assert detail is not None
    assert len(detail["messages"]) == 1

    artifacts = email_query.list_classification_artifacts_for_thread(
        thread_id=thread_id,
        runtime=runtime,
    )
    assert len(artifacts) == 1
    assert artifacts[0]["decision_context"]["trigger_family"] == "manual_thread_reprocess"

    scheduled = create_thread_reminder(
        thread_id=thread_id,
        due_at=datetime(2026, 1, 3, 9, 0, 0, tzinfo=UTC),
        created_by="user",
        task_type="reminder",
        runtime=runtime,
    )
    assert scheduled.status == "accepted"
    assert scheduled.task_id is not None

    tasks = list_thread_scheduled_tasks(thread_id=thread_id, runtime=runtime)
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "reminder"
    completed = complete_thread_task(
        thread_id=thread_id,
        task_id=tasks[0]["id"],
        runtime=runtime,
    )
    assert completed.status == "accepted"
    assert completed.completed is True


def test_email_send_draft_requires_approval(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)
    monkeypatch.setattr("helm_api.services.email_service._runtime", lambda: runtime)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-send-approval")
        )
        draft = SQLAlchemyEmailDraftRepository(session).create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Please approve me",
                approval_status="pending_user",
            )
        )
        draft_id = draft.id

    result = send_draft(draft_id=draft_id)
    assert result["status"] == "rejected"
    assert result["reason"] == "approval_required"


def test_email_send_draft_records_failure_and_preserves_approval(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)
    monkeypatch.setattr("helm_api.services.email_service._runtime", lambda: runtime)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)
        message_repo = SQLAlchemyEmailMessageRepository(session)

        thread = thread_repo.create(NewEmailThread(provider_thread_id="thr-send-fail"))
        draft = draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Approved response",
                draft_subject="Re: Opportunity",
                approval_status="approved",
            )
        )
        draft_id = draft.id
        message_repo.upsert_from_normalized(
            EmailMessage(
                provider_message_id="msg-inbound-1",
                provider_thread_id="thr-send-fail",
                from_address="recruiter@example.com",
                subject="Opportunity",
                body_text="Can you reply?",
                received_at=datetime(2026, 3, 11, 8, 0, tzinfo=UTC),
                normalized_at=datetime(2026, 3, 11, 8, 0, tzinfo=UTC),
            ),
            email_thread_id=thread.id,
        )

    monkeypatch.setattr(
        "email_agent.send.send_reply",
        lambda **_: (_ for _ in ()).throw(
            GmailSendError("unknown_delivery_state", "Provider timed out after accept")
        ),
    )

    result = send_draft(draft_id=draft_id)
    assert result["status"] == "failed"
    assert result["reason"] == "unknown_delivery_state"
    assert result["warning"] is not None

    detail = email_query.get_email_draft_detail(draft_id=draft_id, runtime=runtime)
    assert detail is not None
    assert detail["approval_status"] == "approved"
    assert detail["status"] == "send_failed"
    assert detail["final_sent_message_id"] is None
    assert len(detail["send_attempts"]) == 1
    assert detail["send_attempts"][0]["failure_class"] == "unknown_delivery_state"


def test_email_send_draft_persists_outbound_message_and_blocks_duplicates(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)
    monkeypatch.setattr("helm_api.services.email_service._runtime", lambda: runtime)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)
        message_repo = SQLAlchemyEmailMessageRepository(session)

        thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-send-success",
                business_state="waiting_on_user",
                visible_labels=("Action",),
                current_summary="Need to respond",
                latest_confidence_band="High",
                resurfacing_source="new_message",
                action_reason="reply_needed",
            )
        )
        draft = draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Thanks, I am available.",
                draft_subject="Re: Intro call",
                approval_status="approved",
                status="send_failed",
            )
        )
        draft_id = draft.id
        message_repo.upsert_from_normalized(
            EmailMessage(
                provider_message_id="msg-inbound-2",
                provider_thread_id="thr-send-success",
                from_address="recruiter@example.com",
                subject="Intro call",
                body_text="Can you send times?",
                received_at=datetime(2026, 3, 11, 8, 0, tzinfo=UTC),
                normalized_at=datetime(2026, 3, 11, 8, 0, tzinfo=UTC),
            ),
            email_thread_id=thread.id,
        )

    monkeypatch.setattr(
        "email_agent.send.send_reply",
        lambda **_: GmailSendResult(
            provider_message_id="gmail-out-1",
            provider_thread_id="thr-send-success",
            from_address="me@example.com",
            to_address="recruiter@example.com",
            subject="Re: Intro call",
            body_text="Thanks, I am available.",
            sent_at=datetime(2026, 3, 11, 8, 5, tzinfo=UTC),
        ),
    )

    result = send_draft(draft_id=draft_id)
    assert result["status"] == "accepted"
    assert result["sent"] is True
    assert result["final_sent_message_id"] is not None

    detail = email_query.get_email_draft_detail(draft_id=draft_id, runtime=runtime)
    assert detail is not None
    assert detail["final_sent_message_id"] == result["final_sent_message_id"]
    assert detail["status"] == "generated"
    assert detail["send_attempts"][0]["status"] == "succeeded"
    attempts = list_send_attempts(draft_id=draft_id)
    assert len(attempts) == 1
    assert attempts[0]["provider_message_id"] == "gmail-out-1"

    duplicate = send_draft(draft_id=draft_id)
    assert duplicate["status"] == "rejected"
    assert duplicate["reason"] == "duplicate_send"

    detail = email_query.get_email_draft_detail(draft_id=draft_id, runtime=runtime)
    assert detail is not None
    assert len(detail["send_attempts"]) == 2
    assert detail["send_attempts"][0]["failure_class"] == "duplicate_send"


def test_email_draft_detail_includes_transition_audits() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)

        thread = thread_repo.create(NewEmailThread(provider_thread_id="thr-draft-detail"))
        proposal = proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Reply with availability",
                confidence_band="High",
            )
        )
        draft = runtime.create_email_draft(
            email_thread_id=thread.id,
            action_proposal_id=proposal.id,
            draft_body="Thanks for reaching out.",
            draft_subject="Re: Opportunity",
            reasoning_artifact={
                "schema_version": "email_draft_reasoning_v1",
                "prompt_context": {"stage": "generate"},
                "model_metadata": {"provider": "openai"},
                "reasoning_payload": {"tone": "professional"},
                "refinement_metadata": {"event_type": "generation"},
            },
        )

    approve_result = approve_draft(draft.id, runtime=runtime)
    assert approve_result.ok is True

    detail = email_query.get_email_draft_detail(draft_id=draft.id, runtime=runtime)
    audits = email_query.list_draft_transition_audits_for_draft(draft_id=draft.id, runtime=runtime)
    reasoning_artifacts = email_query.list_draft_reasoning_artifacts_for_draft(
        draft_id=draft.id,
        runtime=runtime,
    )

    assert detail is not None
    assert detail["id"] == draft.id
    assert detail["approval_status"] == "approved"
    assert detail["draft_reasoning_artifact_ref"] == reasoning_artifacts[0]["artifact_ref"]
    assert len(detail["transition_audits"]) == 1
    assert detail["transition_audits"][0]["action"] == "approve"
    assert len(detail["reasoning_artifacts"]) == 1
    assert detail["reasoning_artifacts"][0]["schema_version"] == "email_draft_reasoning_v1"
    assert len(audits) == 1
    assert audits[0]["to_status"] == "approved"
    assert len(reasoning_artifacts) == 1
    assert reasoning_artifacts[0]["email_draft_id"] == draft.id


def test_email_service_lists_global_scheduled_tasks() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        first = thread_repo.create(NewEmailThread(provider_thread_id="thr-task-1"))
        second = thread_repo.create(NewEmailThread(provider_thread_id="thr-task-2"))
        first_id = first.id
        second_id = second.id

    create_thread_reminder(
        thread_id=second_id,
        due_at=datetime(2026, 1, 3, 9, 0, 0, tzinfo=UTC),
        created_by="user",
        task_type="followup",
        runtime=runtime,
    )
    scheduled = create_thread_reminder(
        thread_id=first_id,
        due_at=datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC),
        created_by="user",
        task_type="reminder",
        runtime=runtime,
    )
    assert scheduled.task_id is not None
    complete_thread_task(
        thread_id=first_id,
        task_id=scheduled.task_id,
        runtime=runtime,
    )

    all_tasks = list_scheduled_tasks(runtime=runtime, limit=10)
    pending_tasks = list_scheduled_tasks(runtime=runtime, status="pending", limit=10)
    completed_tasks = list_scheduled_tasks(runtime=runtime, status="completed", limit=10)

    assert [task["task_type"] for task in all_tasks] == ["reminder", "followup"]
    assert [task["status"] for task in all_tasks] == ["completed", "pending"]
    assert len(pending_tasks) == 1
    assert pending_tasks[0]["task_type"] == "followup"
    assert len(completed_tasks) == 1
    assert completed_tasks[0]["task_type"] == "reminder"


def test_email_service_completes_task_from_global_queue() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-task-complete")
        )
        thread_id = thread.id

    scheduled = create_thread_reminder(
        thread_id=thread_id,
        due_at=datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC),
        created_by="user",
        task_type="reminder",
        runtime=runtime,
    )
    assert scheduled.task_id is not None

    completed = complete_scheduled_task(task_id=scheduled.task_id, runtime=runtime)

    assert completed.status == "accepted"
    assert completed.thread_id == thread_id
    assert completed.completed is True


def test_email_thread_override_updates_state(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(
                provider_thread_id="thr-api-override",
                business_state="waiting_on_user",
                visible_labels=("Action",),
                current_summary="Need reply",
            )
        )
        thread_id = thread.id

    monkeypatch.setattr("helm_api.services.email_service._runtime", lambda: runtime)

    result = override_thread(
        thread_id=thread_id,
        business_state="resolved",
        visible_labels=[],
        current_summary="Resolved manually",
        latest_confidence_band="High",
        action_reason="user_marked_done",
    )

    assert result["status"] == "accepted"
    assert result["thread"]["business_state"] == "resolved"
    assert result["thread"]["visible_labels"] == []
    assert result["thread"]["resurfacing_source"] == "user_override"
