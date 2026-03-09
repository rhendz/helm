from helm_storage.db import Base
from helm_storage.repositories.action_items import (
    ActionItemCreate,
    SQLAlchemyActionItemRepository,
)
from helm_storage.repositories.digest_items import (
    DigestItemCreate,
    SQLAlchemyDigestItemRepository,
)
from helm_storage.repositories.draft_replies import (
    DraftReplyCreate,
    SQLAlchemyDraftReplyRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_action_item_repository_happy_path() -> None:
    session = make_session()
    repo = SQLAlchemyActionItemRepository(session)

    created = repo.create(
        ActionItemCreate(
            title="Reply to recruiter",
            description="Send availability for interview",
            priority=1,
            source_type="email",
            source_id="msg_123",
        )
    )

    open_items = repo.list_open()

    assert created.id is not None
    assert len(open_items) == 1
    assert open_items[0].title == "Reply to recruiter"
    assert open_items[0].source_id == "msg_123"



def test_draft_reply_repository_happy_path() -> None:
    session = make_session()
    repo = SQLAlchemyDraftReplyRepository(session)

    created = repo.create(
        DraftReplyCreate(
            channel_type="email",
            thread_id="thread_42",
            draft_text="Thanks for reaching out. Happy to discuss next week.",
            tone="warm",
        )
    )

    pending = repo.list_pending()

    assert created.id is not None
    assert created.status == "pending"
    assert len(pending) == 1
    assert pending[0].thread_id == "thread_42"



def test_digest_item_repository_happy_path() -> None:
    session = make_session()
    repo = SQLAlchemyDigestItemRepository(session)

    created = repo.create(
        DigestItemCreate(
            domain="opportunity",
            title="Recruiter follow-up due",
            summary="A high-priority recruiter thread needs a response today.",
            priority=1,
        )
    )

    recent = repo.list_recent(limit=5)

    assert created.id is not None
    assert len(recent) == 1
    assert recent[0].domain == "opportunity"
    assert recent[0].title == "Recruiter follow-up due"
