from datetime import UTC, datetime

from helm_api.services import email_service


def test_ingest_manual_email_messages_normalizes_failures_and_processes_valid(
    monkeypatch,
) -> None:  # noqa: ANN001
    class _Message:
        provider_message_id = "msg-1"
        provider_thread_id = "thread-1"
        from_address = "sender@example.com"
        subject = "Hello"
        body_text = "Body"
        received_at = datetime(2026, 1, 2, 8, 0, tzinfo=UTC)
        normalized_at = datetime(2026, 1, 2, 8, 1, tzinfo=UTC)
        source = "gmail"

    class _Result:
        email_thread_id = 10

    monkeypatch.setattr(
        email_service,
        "pull_new_messages_report",
        lambda manual_payload: type(
            "Report",
            (),
            {
                "messages": [_Message()],
                "failure_counts": {"missing_id": 1},
            },
        )(),
    )
    monkeypatch.setattr(email_service, "_runtime", lambda: object())
    monkeypatch.setattr(email_service, "build_email_triage_graph", lambda: object())
    monkeypatch.setattr(
        email_service,
        "process_inbound_email_message",
        lambda *args, **kwargs: _Result(),
    )
    monkeypatch.setattr(
        email_service,
        "record_agent_run",
        lambda *, agent_name, source_type, source_id, execute: execute(),
    )

    result = email_service.ingest_manual_email_messages(
        source_type="email_manual",
        messages=[{"id": "msg-1"}, {"threadId": "missing-id"}],
    )

    assert result["status"] == "accepted"
    assert result["message_count"] == 1
    assert result["processed_count"] == 1
    assert result["thread_count"] == 1
    assert result["failed_message_count"] == 1
    assert result["normalization_failures"] == {"missing_id": 1}


def test_plan_seed_email_messages_returns_bucketed_thread_report(monkeypatch) -> None:  # noqa: ANN001
    class _Message:
        provider_message_id = "msg-1"
        provider_thread_id = "thread-1"
        from_address = "recruiter@example.com"
        subject = "Interview follow-up"
        body_text = "Body"
        received_at = datetime(2026, 1, 2, 8, 0, tzinfo=UTC)
        normalized_at = datetime(2026, 1, 2, 8, 1, tzinfo=UTC)
        source = "gmail"

    monkeypatch.setattr(
        email_service,
        "pull_new_messages_report",
        lambda manual_payload: type(
            "Report",
            (),
            {
                "messages": [_Message()],
                "failure_counts": {"missing_id": 1},
            },
        )(),
    )

    result = email_service.plan_seed_email_messages(
        source_type="email_manual",
        messages=[{"id": "msg-1"}, {"threadId": "missing-id"}],
    )

    assert result["status"] == "accepted"
    assert result["thread_count"] == 1
    assert result["bucket_counts"]["deep_seed"] == 1
    assert result["bucket_thread_ids"]["deep_seed"] == ["thread-1"]
    assert result["failed_message_count"] == 1
