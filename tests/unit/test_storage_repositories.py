from datetime import UTC, datetime, timedelta

from helm_storage.db import Base
from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
from helm_storage.repositories.contracts import (
    ActionItemRepository,
    DigestItemRepository,
    DraftReplyRepository,
    NewActionItem,
    NewDigestItem,
    NewDraftReply,
)
from helm_storage.repositories.digest_items import SQLAlchemyDigestItemRepository
from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
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
