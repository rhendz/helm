from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from helm_connectors.gmail import normalize_gmail_message, pull_new_messages

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "gmail" / "message_minimal.json"


def test_normalize_gmail_message_maps_core_fields() -> None:
    payload = json.loads(FIXTURE_PATH.read_text())

    message = normalize_gmail_message(payload)

    assert message.provider_message_id == "18f3a1234abc"
    assert message.provider_thread_id == "18f39fff0001"
    assert message.subject == "Following up on Staff Engineer role"
    assert message.from_address == "Recruiter <recruiter@example.com>"
    assert message.body_text.startswith("Hi Ankush")
    assert message.received_at == datetime.fromtimestamp(1710000000000 / 1000, tz=UTC)


def test_pull_new_messages_uses_fetcher_and_normalizes_payloads() -> None:
    payload = json.loads(FIXTURE_PATH.read_text())

    def fetcher(_since: datetime | None, _max_results: int) -> list[dict]:
        return [payload]

    normalized = pull_new_messages(fetcher=fetcher)

    assert len(normalized) == 1
    assert normalized[0]["provider_message_id"] == "18f3a1234abc"
    assert normalized[0]["provider_thread_id"] == "18f39fff0001"
