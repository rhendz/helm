from datetime import UTC, datetime, timedelta

from helm_agents import digest_agent
from sqlalchemy.exc import SQLAlchemyError


class _BrokenSession:
    def __enter__(self) -> object:
        raise SQLAlchemyError("db unavailable")

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


def test_generate_daily_digest_falls_back_on_db_failure(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(digest_agent, "SessionLocal", lambda: _BrokenSession())

    result = digest_agent.generate_daily_digest()

    assert result.action_count == 0
    assert result.digest_item_count == 0
    assert result.linkedin_opportunity_count == 0
    assert result.pending_draft_count == 0
    assert result.ranked_signals == []
    assert "No artifact data available" in result.text


class _Session:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


class _ActionRepo:
    def __init__(self, _session: object) -> None:
        pass

    def list_open(self) -> list[object]:
        return [
            type(
                "Action",
                (),
                {
                    "priority": 1,
                    "title": "Reply recruiter",
                    "created_at": datetime.now(UTC) - timedelta(hours=1),
                },
            )()
        ]


class _DigestRepo:
    def __init__(self, _session: object) -> None:
        pass

    def list_ranked(self, limit: int = 5) -> list[object]:
        assert limit == 5
        return [
            type(
                "Digest",
                (),
                {
                    "priority": 2,
                    "domain": "email",
                    "title": "Hot intro",
                    "created_at": datetime.now(UTC) - timedelta(hours=7),
                },
            )()
        ]


class _DraftRepo:
    def __init__(self, _session: object) -> None:
        pass

    def list_pending(self) -> list[object]:
        return [
            type(
                "Draft",
                (),
                {
                    "id": 7,
                    "channel_type": "email",
                    "status": "pending",
                    "updated_at": datetime.now(UTC) - timedelta(days=3),
                },
            )()
        ]


class _OpportunityRepo:
    def __init__(self, _session: object) -> None:
        pass

    def list_open(self, *, limit: int) -> list[object]:
        assert limit == 5
        return [
            type(
                "Opportunity",
                (),
                {
                    "role_title": "Staff Engineer",
                    "company": "Acme",
                    "priority_score": 80,
                    "created_at": datetime.now(UTC) - timedelta(minutes=15),
                },
            )()
        ]


def test_generate_daily_digest_uses_ranked_sources(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(digest_agent, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(digest_agent, "SQLAlchemyActionItemRepository", _ActionRepo)
    monkeypatch.setattr(digest_agent, "SQLAlchemyDigestItemRepository", _DigestRepo)
    monkeypatch.setattr(digest_agent, "SQLAlchemyOpportunityRepository", _OpportunityRepo)
    monkeypatch.setattr(digest_agent, "SQLAlchemyDraftReplyRepository", _DraftRepo)

    result = digest_agent.generate_daily_digest()

    assert result.action_count == 1
    assert result.digest_item_count == 1
    assert result.linkedin_opportunity_count == 1
    assert result.pending_draft_count == 1
    assert result.stale_pending_draft_count == 1
    assert "Actions:" in result.text
    assert "Priority Signals:" in result.text
    assert "[linkedin] Staff Engineer @ Acme (high-urgency, new)" in result.text
    assert "[action] Reply recruiter (high-urgency, new)" in result.text
    assert "[email] Hot intro (medium-urgency, recent)" in result.text
    assert "[draft] Draft #7 (email) (medium-urgency, stale)" in result.text
    assert "Pending Drafts:" in result.text
    assert "Stale Approvals:" in result.text
    assert "#7" in result.text
    assert result.ranked_signals[0].reasons.keys() == {"source", "urgency", "freshness"}
    assert result.ranked_signals[0].reasons["source"] in {"linkedin", "action"}
    assert result.ranked_signals[-1].reasons["freshness"] == "stale"
