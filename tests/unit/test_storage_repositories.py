from datetime import UTC, datetime, timedelta

from helm_storage.db import Base
from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.classification_artifacts import (
    SQLAlchemyClassificationArtifactRepository,
)
from helm_storage.repositories.contracts import (
    ActionItemRepository,
    ActionProposalRepository,
    ClassificationArtifactRepository,
    DigestItemRepository,
    DraftReasoningArtifactRepository,
    DraftReplyRepository,
    EmailAgentConfigPatch,
    EmailAgentConfigRepository,
    EmailDraftRepository,
    EmailThreadRepository,
    NewActionItem,
    NewActionProposal,
    NewClassificationArtifact,
    NewDigestItem,
    NewDraftReasoningArtifact,
    NewDraftReply,
    NewEmailDraft,
    NewEmailThread,
    NewScheduledThreadTask,
    ScheduledThreadTaskRepository,
)
from helm_storage.repositories.digest_items import SQLAlchemyDigestItemRepository
from helm_storage.repositories.draft_reasoning_artifacts import (
    SQLAlchemyDraftReasoningArtifactRepository,
)
from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
from helm_storage.repositories.email_agent_config import SQLAlchemyEmailAgentConfigRepository
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_storage.repositories.scheduled_thread_tasks import (
    SQLAlchemyScheduledThreadTaskRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_action_item_repository_contract_and_ordering() -> None:
    with _session() as session:
        repo = SQLAlchemyActionItemRepository(session)
        assert isinstance(repo, ActionItemRepository)

        repo.create(
            NewActionItem(source_type="email", source_id="m-1", title="Medium", priority=2)
        )
        repo.create(
            NewActionItem(source_type="email", source_id="m-2", title="Highest", priority=1)
        )
        repo.create(
            NewActionItem(
                source_type="email",
                source_id="m-3",
                title="Closed",
                priority=1,
                status="done",
            )
        )

        open_items = repo.list_open()
        assert [item.title for item in open_items] == ["Highest", "Medium"]

        fetched = repo.get_by_id(open_items[0].id)
        assert fetched is not None
        assert fetched.title == "Highest"
        assert (
            repo.get_open_by_source(source_type="email", source_id="m-2") is not None
        )


def test_draft_reply_repository_contract_and_transitions() -> None:
    with _session() as session:
        repo = SQLAlchemyDraftReplyRepository(session)
        assert isinstance(repo, DraftReplyRepository)

        first = repo.create(NewDraftReply(thread_id="thr-1", draft_text="reply one"))
        second = repo.create(NewDraftReply(thread_id="thr-1", draft_text="reply two"))

        assert [draft.id for draft in repo.list_pending()] == [second.id, first.id]

        assert repo.snooze(first.id) is True
        assert repo.approve(first.id) is True
        assert repo.approve(99999) is False

        updated = repo.get_by_id(first.id)
        assert updated is not None
        assert updated.status == "approved"
        latest = repo.get_latest_for_thread(thread_id="thr-1")
        assert latest is not None
        assert latest.id == second.id
        assert repo.get_latest_for_thread(thread_id="missing-thread") is None


def test_draft_reply_repository_stale_and_requeue_behavior() -> None:
    with _session() as session:
        repo = SQLAlchemyDraftReplyRepository(session)
        draft = repo.create(NewDraftReply(thread_id="thr-stale", draft_text="reply"))
        row = repo.get_by_id(draft.id)
        assert row is not None
        row.updated_at = datetime.now(UTC) - timedelta(hours=100)
        row.status = "snoozed"
        session.add(row)
        session.commit()

        stale = repo.list_stale(stale_after_hours=72, include_snoozed=True)
        assert [item.id for item in stale] == [draft.id]

        assert repo.requeue(draft.id) is True
        refreshed = repo.get_by_id(draft.id)
        assert refreshed is not None
        assert refreshed.status == "pending"


def test_digest_item_repository_contract_and_filters() -> None:
    with _session() as session:
        repo = SQLAlchemyDigestItemRepository(session)
        assert isinstance(repo, DigestItemRepository)

        repo.create(NewDigestItem(domain="email", title="Low", summary="...", priority=3))
        repo.create(NewDigestItem(domain="study", title="Study", summary="...", priority=2))
        repo.create(NewDigestItem(domain="email", title="High", summary="...", priority=1))

        top_all = repo.list_top(limit=2)
        assert [item.title for item in top_all] == ["High", "Study"]

        top_email = repo.list_top(limit=5, domain="email")
        assert [item.title for item in top_email] == ["High", "Low"]
        assert (
            repo.find_matching(
                domain="email",
                title="High",
                summary="...",
                related_action_id=None,
            )
            is not None
        )


def test_email_thread_repository_contract_and_state_updates() -> None:
    with _session() as session:
        repo = SQLAlchemyEmailThreadRepository(session)
        assert isinstance(repo, EmailThreadRepository)

        created = repo.get_or_create(
            NewEmailThread(
                provider_thread_id="thr-100",
                business_state="waiting_on_user",
                visible_labels=("Action", "Urgent"),
                current_summary="Need to reply",
                latest_confidence_band="High",
                resurfacing_source="new_message",
                action_reason="reply_needed",
            )
        )
        duplicate = repo.get_or_create(NewEmailThread(provider_thread_id="thr-100"))

        assert duplicate.id == created.id

        updated = repo.update_state(
            created.id,
            business_state="waiting_on_other_party",
            visible_labels=("Action",),
            latest_confidence_band="Medium",
            resurfacing_source="stale_followup",
            action_reason="followup_due",
            current_summary="Waiting on response",
        )
        assert updated is not None
        assert updated.business_state == "waiting_on_other_party"
        assert updated.visible_labels == "Action"
        assert updated.resurfacing_source == "stale_followup"


def test_action_proposal_and_email_draft_repositories_preserve_lineage() -> None:
    with _session() as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)

        assert isinstance(proposal_repo, ActionProposalRepository)
        assert isinstance(draft_repo, EmailDraftRepository)

        thread = thread_repo.create(NewEmailThread(provider_thread_id="thr-200"))
        proposal = proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Recruiter asked for availability",
                confidence_band="High",
            )
        )
        draft = draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                draft_body="Thanks, I am interested.",
                draft_subject="Re: Intro",
            )
        )

        assert proposal_repo.get_latest_for_thread(email_thread_id=thread.id) is not None
        assert draft_repo.get_latest_for_thread(email_thread_id=thread.id) is not None
        assert draft_repo.set_approval_status(draft.id, approval_status="approved") is True
        refreshed = draft_repo.get_by_id(draft.id)
        assert refreshed is not None
        assert refreshed.approval_status == "approved"


def test_draft_reasoning_artifact_repository_preserves_history() -> None:
    with _session() as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)
        artifact_repo = SQLAlchemyDraftReasoningArtifactRepository(session)

        assert isinstance(artifact_repo, DraftReasoningArtifactRepository)

        thread = thread_repo.create(NewEmailThread(provider_thread_id="thr-201"))
        proposal = proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Reply with availability",
                confidence_band="High",
            )
        )
        draft = draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                draft_body="Thanks for reaching out.",
                draft_subject="Re: Opportunity",
            )
        )

        first = artifact_repo.create(
            NewDraftReasoningArtifact(
                email_draft_id=draft.id,
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                schema_version="email_draft_reasoning_v1",
                prompt_context={"stage": "generate"},
                model_metadata={"provider": "openai"},
                reasoning_payload={"tone": "professional"},
                refinement_metadata={"event_type": "generation"},
            )
        )
        second = artifact_repo.create(
            NewDraftReasoningArtifact(
                email_draft_id=draft.id,
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                schema_version="email_draft_reasoning_v1",
                prompt_context={"stage": "refine"},
                model_metadata={"provider": "openai"},
                reasoning_payload={"tone": "warmer"},
                refinement_metadata={"event_type": "refinement"},
            )
        )

        assert draft_repo.set_reasoning_artifact_ref(
            draft.id,
            artifact_ref=second.internal_uuid,
        )

        artifacts = artifact_repo.list_for_draft(email_draft_id=draft.id)
        assert [artifact.id for artifact in artifacts] == [second.id, first.id]

        refreshed = draft_repo.get_by_id(draft.id)
        assert refreshed is not None
        assert refreshed.draft_reasoning_artifact_ref == second.internal_uuid


def test_classification_artifact_repository_preserves_lineage() -> None:
    with _session() as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        message_repo = SQLAlchemyEmailMessageRepository(session)
        artifact_repo = SQLAlchemyClassificationArtifactRepository(session)

        assert isinstance(artifact_repo, ClassificationArtifactRepository)

        thread = thread_repo.create(NewEmailThread(provider_thread_id="thr-220"))
        message = message_repo.upsert_from_normalized(
            type(
                "Message",
                (),
                {
                    "provider_message_id": "msg-220",
                    "provider_thread_id": "thr-220",
                    "from_address": "recruiter@example.com",
                    "subject": "Checking in",
                    "body_text": "Any update?",
                    "snippet": "Any update?",
                    "received_at": datetime.now(UTC),
                    "normalized_at": datetime.now(UTC),
                    "source": "gmail",
                },
            )(),
            email_thread_id=thread.id,
            direction="inbound",
        )

        artifact = artifact_repo.create(
            NewClassificationArtifact(
                email_thread_id=thread.id,
                email_message_id=message.id,
                classification="urgent",
                priority_score=1,
                business_state="waiting_on_user",
                visible_labels=("Action", "Urgent"),
                action_reason="reply_needed",
                resurfacing_source="new_message",
                confidence_band="High",
                decision_context={"draft_reply_required": True},
                model_name="rule_based_triage",
                prompt_version="email_triage_v1",
            )
        )

        assert artifact_repo.list_for_thread(email_thread_id=thread.id)[0].id == artifact.id
        assert artifact_repo.list_for_message(email_message_id=message.id)[0].id == artifact.id


def test_scheduled_thread_task_repository_lists_due_items_and_marks_completed() -> None:
    with _session() as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        task_repo = SQLAlchemyScheduledThreadTaskRepository(session)
        assert isinstance(task_repo, ScheduledThreadTaskRepository)

        thread = thread_repo.create(NewEmailThread(provider_thread_id="thr-300"))
        due_task = task_repo.create(
            NewScheduledThreadTask(
                email_thread_id=thread.id,
                task_type="followup",
                created_by="system",
                due_at=datetime.now(UTC) - timedelta(hours=1),
                reason="followup_due",
            )
        )
        task_repo.create(
            NewScheduledThreadTask(
                email_thread_id=thread.id,
                task_type="reminder",
                created_by="user",
                due_at=datetime.now(UTC) + timedelta(hours=1),
                reason="reminder_due",
            )
        )

        due = task_repo.list_due(due_before=datetime.now(UTC))
        assert [item.id for item in due] == [due_task.id]
        assert task_repo.mark_completed(due_task.id) is True


def test_email_agent_config_repository_creates_singleton_config() -> None:
    with _session() as session:
        repo = SQLAlchemyEmailAgentConfigRepository(session)
        assert isinstance(repo, EmailAgentConfigRepository)

        initial = repo.get_or_create()
        assert initial.approval_required_before_send is True
        assert initial.default_follow_up_business_days == 3

        updated = repo.update(
            EmailAgentConfigPatch(
                approval_required_before_send=False,
                default_follow_up_business_days=5,
                last_history_cursor="cursor-1",
            )
        )
        assert updated.id == initial.id
        assert updated.approval_required_before_send is False
        assert updated.default_follow_up_business_days == 5
        assert updated.last_history_cursor == "cursor-1"
