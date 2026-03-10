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
        received_at = None
        normalized_at = None
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
        "run_email_triage_workflow",
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
