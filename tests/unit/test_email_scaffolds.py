from datetime import UTC, datetime

import pytest
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
