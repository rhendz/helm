from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from helm_observability.logging import get_logger


@dataclass(slots=True, frozen=True)
class NormalizedGmailMessage:
    """Internal normalization contract for inbound Gmail messages."""

    provider_message_id: str
    provider_thread_id: str
    from_address: str
    subject: str
    body_text: str
    received_at: datetime
    normalized_at: datetime
    source: str = "gmail"


def _parse_received_at(value: Any, *, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            # Gmail commonly sends `internalDate` as ms since epoch.
            return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
        except ValueError:
            pass
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return fallback
    return fallback


def normalize_message(
    raw_payload: Mapping[str, Any], *, normalized_at: datetime | None = None
) -> NormalizedGmailMessage:
    now = normalized_at or datetime.now(tz=UTC)
    provider_message_id = str(raw_payload.get("id", "")).strip()
    if not provider_message_id:
        raise ValueError("Gmail payload must include non-empty `id`.")

    provider_thread_id = str(raw_payload.get("threadId", provider_message_id)).strip()
    headers = raw_payload.get("headers")
    header_map = headers if isinstance(headers, Mapping) else {}
    from_address = str(raw_payload.get("from") or header_map.get("From") or "").strip()
    subject = str(raw_payload.get("subject") or header_map.get("Subject") or "").strip()
    body_text = str(raw_payload.get("body_text") or raw_payload.get("snippet") or "").strip()
    received_at_raw = raw_payload.get("received_at", raw_payload.get("internalDate"))
    received_at = _parse_received_at(received_at_raw, fallback=now)

    return NormalizedGmailMessage(
        provider_message_id=provider_message_id,
        provider_thread_id=provider_thread_id or provider_message_id,
        from_address=from_address,
        subject=subject,
        body_text=body_text,
        received_at=received_at,
        normalized_at=now,
    )


def pull_new_messages(
    manual_payload: list[dict[str, Any]] | None = None,
) -> list[NormalizedGmailMessage]:
    logger = get_logger("helm_connectors.gmail")
    if manual_payload is not None:
        logger.info("gmail_pull_manual_payload", count=len(manual_payload))
        return [normalize_message(item) for item in manual_payload]

    logger.info("gmail_pull_stub")
    # TODO(v1-phase2-rhe14): implement Gmail fetch path and pass provider payloads through
    # normalize_message before returning artifacts to orchestration.
    return []
