import pytest
from email_agent.operator import approve_draft
from email_agent.triage import (
    build_email_triage_graph,
    process_inbound_email_message,
    run_email_triage_workflow,
)
from email_agent.types import EmailMessage
from helm_providers.gmail import normalize_message
from helm_runtime.email_agent import build_email_agent_runtime
from helm_storage.db import Base
from helm_storage.models import (
    ActionProposalORM,
    AgentRunORM,
    ClassificationArtifactORM,
    DigestItemORM,
    DraftReasoningArtifactORM,
    EmailDraftORM,
    EmailMessageORM,
    EmailThreadORM,
)
from helm_storage.repositories.agent_runs import AgentRunStatus
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def test_email_triage_graph_scaffold_result_shape() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    message = normalize_message(
        {
            "id": "msg-3",
            "threadId": "thr-3",
            "from": "sender@example.com",
            "subject": "Status update",
            "snippet": "Quick update on this.",
        }
    )

    graph = build_email_triage_graph()
    result = process_inbound_email_message(
        _email_message(message),
        graph=graph,
        runtime=build_email_agent_runtime(session_local),
    )

    assert result.message_id == "msg-3"
    assert result.trigger_family == "new_thread_inbound"
    assert result.classification == "unclassified"
    assert result.priority_score == 3
    assert result.action_item_required is False
    assert result.draft_reply_required is False
    assert result.digest_item_required is False
    assert result.workflow_status == "completed"


def test_email_triage_persists_artifacts_and_is_idempotent_for_repeated_runs() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    message = normalize_message(
        {
            "id": "msg-4",
            "threadId": "thr-4",
            "from": "recruiter@example.com",
            "subject": "Staff Backend role",
            "snippet": "Would you be open to an interview?",
        }
    )

    graph = build_email_triage_graph()
    first_result = process_inbound_email_message(
        _email_message(message),
        graph=graph,
        runtime=build_email_agent_runtime(session_local),
    )
    second_result = process_inbound_email_message(
        _email_message(message),
        graph=graph,
        runtime=build_email_agent_runtime(session_local),
    )

    assert first_result.action_item_required is True
    assert first_result.draft_reply_required is True
    assert first_result.digest_item_required is True
    assert first_result.email_thread_id is not None
    assert first_result.action_proposal_id is not None
    assert first_result.email_draft_id is not None
    assert first_result.digest_item_id is not None

    assert second_result.email_thread_id == first_result.email_thread_id
    assert first_result.trigger_family == "new_thread_inbound"
    assert second_result.trigger_family == "existing_thread_inbound"
    assert second_result.action_proposal_id == first_result.action_proposal_id
    assert second_result.email_draft_id == first_result.email_draft_id
    assert second_result.digest_item_id == first_result.digest_item_id

    with Session(engine) as session:
        email_messages = list(session.execute(select(EmailMessageORM)).scalars().all())
        email_threads = list(session.execute(select(EmailThreadORM)).scalars().all())
        action_proposals = list(session.execute(select(ActionProposalORM)).scalars().all())
        email_drafts = list(session.execute(select(EmailDraftORM)).scalars().all())
        draft_reasoning_artifacts = list(
            session.execute(select(DraftReasoningArtifactORM)).scalars().all()
        )
        classification_artifacts = list(
            session.execute(select(ClassificationArtifactORM)).scalars().all()
        )
        digest_items = list(session.execute(select(DigestItemORM)).scalars().all())
        agent_runs = list(session.execute(select(AgentRunORM)).scalars().all())

    assert len(email_messages) == 1
    assert email_messages[0].processed_at is not None
    assert email_messages[0].email_thread_id == first_result.email_thread_id
    assert len(email_threads) == 1
    assert email_threads[0].provider_thread_id == "thr-4"
    assert email_threads[0].business_state == "waiting_on_user"
    assert email_threads[0].visible_labels == "Action"
    assert len(action_proposals) == 1
    assert len(email_drafts) == 1
    assert email_drafts[0].draft_reasoning_artifact_ref is not None
    assert "Draft reply stub" not in email_drafts[0].draft_body
    assert "TODO: personalize response" not in email_drafts[0].draft_body
    assert "I'm interested in learning more about this opportunity." in email_drafts[0].draft_body
    assert len(draft_reasoning_artifacts) == 2
    assert all(
        artifact.email_draft_id == email_drafts[0].id for artifact in draft_reasoning_artifacts
    )
    assert all(
        artifact.action_proposal_id == action_proposals[0].id
        for artifact in draft_reasoning_artifacts
    )
    assert all(
        artifact.schema_version == "email_draft_reasoning_v1"
        for artifact in draft_reasoning_artifacts
    )
    event_types = {
        artifact.refinement_metadata["event_type"] for artifact in draft_reasoning_artifacts
    }
    assert event_types == {"generation", "refinement"}
    generators = {artifact.model_metadata["generator"] for artifact in draft_reasoning_artifacts}
    assert generators == {"deterministic_grounded_reply"}
    assert len(classification_artifacts) == 2
    assert classification_artifacts[0].email_thread_id == first_result.email_thread_id
    assert classification_artifacts[0].email_message_id == email_messages[0].id
    assert classification_artifacts[0].decision_context["trigger_family"] == "new_thread_inbound"
    assert (
        classification_artifacts[1].decision_context["trigger_family"] == "existing_thread_inbound"
    )
    assert len(digest_items) == 1
    assert len(agent_runs) == 2
    assert all(run.status == AgentRunStatus.SUCCEEDED.value for run in agent_runs)


def test_classification_artifact_failure_does_not_revert_thread_truth() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    runtime = build_email_agent_runtime(session_local)
    original_create = runtime.create_classification_artifact

    def _fail_create(**kwargs):  # noqa: ANN001
        raise RuntimeError("artifact write failed")

    runtime.create_classification_artifact = _fail_create  # type: ignore[method-assign]

    message = normalize_message(
        {
            "id": "msg-fail-1",
            "threadId": "thr-fail-1",
            "from": "recruiter@example.com",
            "subject": "Urgent role",
            "snippet": "Need a reply today.",
        }
    )

    with pytest.raises(RuntimeError, match="artifact write failed"):
        run_email_triage_workflow(
            _email_message(message),
            graph=build_email_triage_graph(),
            runtime=runtime,
        )

    runtime.create_classification_artifact = original_create  # type: ignore[method-assign]

    with Session(engine) as session:
        thread = session.execute(select(EmailThreadORM)).scalars().one()
        artifacts = list(session.execute(select(ClassificationArtifactORM)).scalars().all())

    assert thread.provider_thread_id == "thr-fail-1"
    assert thread.business_state == "waiting_on_user"
    assert thread.visible_labels == "Action,Urgent"
    assert artifacts == []


def test_email_triage_consolidates_near_duplicate_messages_on_same_thread() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    first_message = normalize_message(
        {
            "id": "msg-10-a",
            "threadId": "thr-10",
            "from": "recruiter@example.com",
            "subject": "Staff Backend role",
            "snippet": "Would you be open to an interview?",
        }
    )
    second_message = normalize_message(
        {
            "id": "msg-10-b",
            "threadId": "thr-10",
            "from": "recruiter@example.com",
            "subject": "Staff Backend role",
            "snippet": "Checking in on this thread.",
        }
    )

    graph = build_email_triage_graph()
    first_result = process_inbound_email_message(
        _email_message(first_message),
        graph=graph,
        runtime=build_email_agent_runtime(session_local),
    )
    second_result = process_inbound_email_message(
        _email_message(second_message),
        graph=graph,
        runtime=build_email_agent_runtime(session_local),
    )

    assert first_result.email_thread_id is not None
    assert first_result.trigger_family == "new_thread_inbound"
    assert second_result.trigger_family == "existing_thread_inbound"
    assert second_result.email_thread_id == first_result.email_thread_id
    assert first_result.action_proposal_id is not None
    assert second_result.action_proposal_id == first_result.action_proposal_id
    assert first_result.email_draft_id is not None
    assert second_result.email_draft_id == first_result.email_draft_id

    with Session(engine) as session:
        email_threads = list(session.execute(select(EmailThreadORM)).scalars().all())
        action_proposals = list(session.execute(select(ActionProposalORM)).scalars().all())
        email_drafts = list(session.execute(select(EmailDraftORM)).scalars().all())
        email_messages = list(session.execute(select(EmailMessageORM)).scalars().all())

    assert len(email_threads) == 1
    assert len(action_proposals) == 1
    assert len(email_drafts) == 1
    assert len(email_messages) == 2


def test_email_triage_refines_existing_draft_in_place_and_resets_approval_on_change() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    first_message = normalize_message(
        {
            "id": "msg-refine-a",
            "threadId": "thr-refine",
            "from": "recruiter@example.com",
            "subject": "Role intro",
            "snippet": "Would you be interested in chatting?",
        }
    )
    second_message = normalize_message(
        {
            "id": "msg-refine-b",
            "threadId": "thr-refine",
            "from": "recruiter@example.com",
            "subject": "Role intro updated",
            "snippet": "Could you share times for this week?",
        }
    )

    first_result = process_inbound_email_message(
        _email_message(first_message),
        graph=build_email_triage_graph(),
        runtime=runtime,
    )
    assert first_result.email_draft_id is not None
    assert approve_draft(first_result.email_draft_id, runtime=runtime).ok is True

    second_result = process_inbound_email_message(
        _email_message(second_message),
        graph=build_email_triage_graph(),
        runtime=runtime,
    )

    assert second_result.email_draft_id == first_result.email_draft_id

    with Session(engine) as session:
        drafts = list(session.execute(select(EmailDraftORM)).scalars().all())
        reasoning_artifacts = list(
            session.execute(select(DraftReasoningArtifactORM)).scalars().all()
        )

    assert len(drafts) == 1
    assert drafts[0].approval_status == "pending_user"
    assert "If you send over a few times that work on your side" in drafts[0].draft_body
    assert drafts[0].draft_subject == "Role intro updated"
    assert len(reasoning_artifacts) == 2


def test_email_triage_keeps_approval_when_refinement_content_is_unchanged() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    message = normalize_message(
        {
            "id": "msg-same-a",
            "threadId": "thr-same",
            "from": "recruiter@example.com",
            "subject": "Role intro",
            "snippet": "Would you be interested in chatting?",
        }
    )

    first_result = process_inbound_email_message(
        _email_message(message),
        graph=build_email_triage_graph(),
        runtime=runtime,
    )
    assert first_result.email_draft_id is not None
    assert approve_draft(first_result.email_draft_id, runtime=runtime).ok is True

    second_result = process_inbound_email_message(
        _email_message(message),
        graph=build_email_triage_graph(),
        runtime=runtime,
    )

    assert second_result.email_draft_id == first_result.email_draft_id

    with Session(engine) as session:
        drafts = list(session.execute(select(EmailDraftORM)).scalars().all())
        reasoning_artifacts = list(
            session.execute(select(DraftReasoningArtifactORM)).scalars().all()
        )

    assert len(drafts) == 1
    assert drafts[0].approval_status == "approved"
    assert len(reasoning_artifacts) == 2


def test_email_triage_supports_proposal_only_path_without_draft() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    message = normalize_message(
        {
            "id": "msg-review-1",
            "threadId": "thr-review-1",
            "from": "founder@example.com",
            "subject": "FYI review this intro deck",
            "snippet": "Heads up, please review when you have time.",
        }
    )

    result = process_inbound_email_message(
        _email_message(message),
        graph=build_email_triage_graph(),
        runtime=build_email_agent_runtime(session_local),
    )

    assert result.action_item_required is True
    assert result.draft_reply_required is False
    assert result.trigger_family == "new_thread_inbound"
    assert result.action_proposal_id is not None
    assert result.email_draft_id is None

    with Session(engine) as session:
        thread = session.execute(select(EmailThreadORM)).scalars().one()
        proposals = list(session.execute(select(ActionProposalORM)).scalars().all())
        drafts = list(session.execute(select(EmailDraftORM)).scalars().all())

    assert thread.business_state == "waiting_on_user"
    assert thread.action_reason == "awareness_needed"
    assert len(proposals) == 1
    assert proposals[0].proposal_type == "review"
    assert drafts == []


def test_email_triage_routes_uncertain_important_mail_to_needs_review() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    message = normalize_message(
        {
            "id": "msg-review-uncertain-1",
            "threadId": "thr-review-uncertain-1",
            "from": "investor@example.com",
            "subject": "Deck update for today",
            "snippet": "Please take a look when you can.",
        }
    )

    result = process_inbound_email_message(
        _email_message(message),
        graph=build_email_triage_graph(),
        runtime=build_email_agent_runtime(session_local),
    )

    assert result.action_item_required is True
    assert result.draft_reply_required is False
    assert result.trigger_family == "new_thread_inbound"
    assert result.action_proposal_id is not None
    assert result.email_draft_id is None

    with Session(engine) as session:
        thread = session.execute(select(EmailThreadORM)).scalars().one()
        proposals = list(session.execute(select(ActionProposalORM)).scalars().all())
        drafts = list(session.execute(select(EmailDraftORM)).scalars().all())

    assert thread.business_state == "needs_review"
    assert thread.visible_labels == "NeedsReview"
    assert thread.action_reason == "classification_uncertain"
    assert thread.latest_confidence_band == "Low"
    assert len(proposals) == 1
    assert proposals[0].proposal_type == "review"
    assert drafts == []


def test_email_triage_suppresses_low_signal_newsletters() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    message = normalize_message(
        {
            "id": "msg-newsletter-1",
            "threadId": "thr-newsletter-1",
            "from": "updates@example.com",
            "subject": "Weekly newsletter",
            "snippet": "Read more or unsubscribe anytime.",
        }
    )

    result = process_inbound_email_message(
        _email_message(message),
        graph=build_email_triage_graph(),
        runtime=build_email_agent_runtime(session_local),
    )

    assert result.classification == "newsletter"
    assert result.action_item_required is False
    assert result.draft_reply_required is False
    assert result.digest_item_required is False
    assert result.action_proposal_id is None
    assert result.email_draft_id is None

    with Session(engine) as session:
        thread = session.execute(select(EmailThreadORM)).scalars().one()
        proposals = list(session.execute(select(ActionProposalORM)).scalars().all())
        drafts = list(session.execute(select(EmailDraftORM)).scalars().all())
        digests = list(session.execute(select(DigestItemORM)).scalars().all())

    assert thread.business_state == "resolved"
    assert thread.visible_labels == ""
    assert proposals == []
    assert drafts == []
    assert digests == []


def _email_message(message) -> EmailMessage:  # noqa: ANN001
    return EmailMessage(
        provider_message_id=message.provider_message_id,
        provider_thread_id=message.provider_thread_id,
        from_address=message.from_address,
        subject=message.subject,
        body_text=message.body_text,
        received_at=message.received_at,
        normalized_at=message.normalized_at,
        source=message.source,
    )
