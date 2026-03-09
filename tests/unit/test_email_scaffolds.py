from datetime import UTC, datetime

import pytest
from helm_connectors import gmail
from helm_connectors.gmail import normalize_message, pull_new_messages
from helm_orchestration.email_flow import build_email_triage_graph, run_email_triage_workflow


def test_normalize_message_contract() -> None:
    normalized = normalize_message(
        {
            "id": "msg-1",
            "threadId": "thr-1",
            "from": "recruiter@example.com",
            "subject": "Backend role",
            "snippet": "Want to chat about a role?",
            "internalDate": "1734567890000",
        },
        normalized_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    assert normalized.provider_message_id == "msg-1"
    assert normalized.provider_thread_id == "thr-1"
    assert normalized.from_address == "recruiter@example.com"
    assert normalized.subject == "Backend role"
    assert normalized.body_text == "Want to chat about a role?"
    assert normalized.source == "gmail"


def test_normalize_message_requires_message_id() -> None:
    with pytest.raises(ValueError, match="must include non-empty `id`"):
        normalize_message({"threadId": "t-1"})


def test_pull_new_messages_manual_payload_normalizes() -> None:
    messages = pull_new_messages(
        manual_payload=[
            {
                "id": "msg-2",
                "from": "sender@example.com",
                "subject": "Hello",
                "body_text": "Body",
            }
        ]
    )

    assert len(messages) == 1
    assert messages[0].provider_message_id == "msg-2"
    assert messages[0].subject == "Hello"


def test_pull_new_messages_returns_empty_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GMAIL_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("GMAIL_USER_EMAIL", raising=False)
    assert pull_new_messages() == []


def test_pull_new_messages_polling_normalizes_provider_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in {
        "GMAIL_CLIENT_ID": "id",
        "GMAIL_CLIENT_SECRET": "secret",
        "GMAIL_REFRESH_TOKEN": "refresh",
        "GMAIL_USER_EMAIL": "me@example.com",
    }.items():
        monkeypatch.setenv(name, value)

    class FakeGetRequest:
        def __init__(self, message_id: str) -> None:
            self.message_id = message_id

        def execute(self) -> dict[str, object]:
            return {
                "id": self.message_id,
                "threadId": "thr-9",
                "internalDate": "1734567890000",
                "snippet": "snippet fallback",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Subject", "value": "Role update"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": "SGVsbG8gZnJvbSBHbWFpbA"},
                        }
                    ],
                },
            }

    class FakeMessagesResource:
        def list(self, **_: object):
            return self

        def get(self, *, id: str, **_: object) -> FakeGetRequest:
            return FakeGetRequest(id)

        def execute(self) -> dict[str, object]:
            return {"messages": [{"id": "msg-9"}]}

    class FakeUsersResource:
        def messages(self) -> FakeMessagesResource:
            return FakeMessagesResource()

    class FakeService:
        def users(self) -> FakeUsersResource:
            return FakeUsersResource()

    monkeypatch.setattr(gmail, "_build_gmail_service", lambda: FakeService())
    messages = pull_new_messages()

    assert len(messages) == 1
    assert messages[0].provider_message_id == "msg-9"
    assert messages[0].provider_thread_id == "thr-9"
    assert messages[0].from_address == "sender@example.com"
    assert messages[0].subject == "Role update"
    assert messages[0].body_text == "Hello from Gmail"


def test_email_triage_graph_scaffold_result_shape() -> None:
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
    result = run_email_triage_workflow(message, graph=graph)

    assert result.message_id == "msg-3"
    assert result.classification == "unclassified"
    assert result.priority_score == 0
    assert result.action_item_required is False
    assert result.draft_reply_required is False
    assert result.digest_item_required is False
    assert result.workflow_status == "scaffold_completed"
