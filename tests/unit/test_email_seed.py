from datetime import UTC, datetime

from email_agent.seed import plan_seed_threads, summarize_seed_plan
from email_agent.types import EmailMessage


def _message(
    *,
    provider_message_id: str,
    provider_thread_id: str,
    from_address: str,
    subject: str,
    received_at: datetime,
) -> EmailMessage:
    return EmailMessage(
        provider_message_id=provider_message_id,
        provider_thread_id=provider_thread_id,
        from_address=from_address,
        subject=subject,
        body_text="",
        received_at=received_at,
        normalized_at=received_at,
        source="gmail",
    )


def test_plan_seed_threads_routes_threads_into_metadata_buckets() -> None:
    decisions = plan_seed_threads(
        [
            _message(
                provider_message_id="msg-1",
                provider_thread_id="thr-deep",
                from_address="recruiter@example.com",
                subject="Staff opportunity",
                received_at=datetime(2026, 1, 2, 8, 0, tzinfo=UTC),
            ),
            _message(
                provider_message_id="msg-2",
                provider_thread_id="thr-light",
                from_address="friend@example.com",
                subject="Coffee next week",
                received_at=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
            ),
            _message(
                provider_message_id="msg-3",
                provider_thread_id="thr-drop",
                from_address="no-reply@example.com",
                subject="Weekly newsletter",
                received_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
            ),
            _message(
                provider_message_id="msg-4",
                provider_thread_id="thr-repeat",
                from_address="founder@example.com",
                subject="Intro",
                received_at=datetime(2026, 1, 2, 11, 0, tzinfo=UTC),
            ),
            _message(
                provider_message_id="msg-5",
                provider_thread_id="thr-repeat",
                from_address="founder@example.com",
                subject="Re: Intro",
                received_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
            ),
        ]
    )

    by_thread = {item.provider_thread_id: item for item in decisions}
    assert by_thread["thr-deep"].bucket == "deep_seed"
    assert by_thread["thr-light"].bucket == "light_seed_only"
    assert by_thread["thr-drop"].bucket == "do_not_surface"
    assert by_thread["thr-repeat"].bucket == "deep_seed"
    assert by_thread["thr-repeat"].reason == "multi_message_thread"


def test_summarize_seed_plan_counts_threads_per_bucket() -> None:
    decisions = plan_seed_threads(
        [
            _message(
                provider_message_id="msg-1",
                provider_thread_id="thr-a",
                from_address="recruiter@example.com",
                subject="Interview follow-up",
                received_at=datetime(2026, 1, 2, 8, 0, tzinfo=UTC),
            ),
            _message(
                provider_message_id="msg-2",
                provider_thread_id="thr-b",
                from_address="friend@example.com",
                subject="Dinner plans",
                received_at=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
            ),
        ]
    )

    summary = summarize_seed_plan(decisions)

    assert summary["thread_count"] == 2
    assert summary["bucket_counts"] == {
        "deep_seed": 1,
        "light_seed_only": 1,
        "do_not_surface": 0,
    }
    assert summary["bucket_thread_ids"]["deep_seed"] == ["thr-a"]
