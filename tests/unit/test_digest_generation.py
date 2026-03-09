from datetime import UTC, datetime, timedelta

from helm_agents.digest_generation import build_digest_text, rank_digest_items
from helm_agents.digest_query import DigestInputs
from helm_storage.repositories import (
    ActionDigestRecord,
    DigestItemRecord,
    DraftDigestRecord,
    StudyPriorityRecord,
)


def test_rank_digest_items_prioritizes_actionable_high_priority_items() -> None:
    now = datetime(2026, 3, 8, 18, 0, tzinfo=UTC)
    inputs = DigestInputs(
        open_action_items=[
            ActionDigestRecord(
                id=1,
                title="Reply to recruiter",
                description=None,
                priority=1,
                created_at=now - timedelta(hours=2),
            )
        ],
        top_digest_items=[
            DigestItemRecord(
                id=21,
                domain="opportunity",
                title="Follow up with referral",
                summary=None,
                priority=1,
                created_at=now - timedelta(hours=6),
            )
        ],
        pending_drafts=[
            DraftDigestRecord(
                id=32,
                channel_type="email",
                status="pending_approval",
                preview="Draft body",
                created_at=now - timedelta(hours=3),
            )
        ],
        study_priorities=[
            StudyPriorityRecord(
                id=43,
                title="Review dynamic programming mistakes",
                priority=2,
                created_at=now - timedelta(days=45),
            )
        ],
    )

    ranked = rank_digest_items(inputs, now=now)

    assert [item.source_type for item in ranked[:3]] == ["action", "digest", "draft"]
    assert all(item.score >= 50 for item in ranked)


def test_build_digest_text_is_concise_and_action_oriented() -> None:
    now = datetime(2026, 3, 8, 18, 0, tzinfo=UTC)
    inputs = DigestInputs(
        open_action_items=[
            ActionDigestRecord(
                id=7,
                title="Send architecture update",
                description=None,
                priority=1,
                created_at=now,
            )
        ],
        top_digest_items=[],
        pending_drafts=[],
        study_priorities=[],
    )

    output = build_digest_text(inputs, now=now)

    assert output.startswith("Daily Brief")
    assert "1. Send architecture update -> Complete action item #7." in output


def test_build_digest_text_returns_low_noise_fallback_when_no_items_meet_threshold() -> None:
    now = datetime(2026, 3, 8, 18, 0, tzinfo=UTC)
    inputs = DigestInputs(
        open_action_items=[
            ActionDigestRecord(
                id=11,
                title="Archive old note",
                description=None,
                priority=5,
                created_at=now - timedelta(days=90),
            )
        ],
        top_digest_items=[],
        pending_drafts=[],
        study_priorities=[],
    )

    output = build_digest_text(inputs, now=now)

    assert "No urgent items from current artifacts." in output
