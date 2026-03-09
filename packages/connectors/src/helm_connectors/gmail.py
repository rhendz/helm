from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from helm_observability.logging import get_logger

logger = get_logger("helm_connectors.gmail")

GmailMessagePayload = Mapping[str, Any]
GmailFetcher = Callable[[datetime | None, int], list[GmailMessagePayload]]


@dataclass(slots=True)
class NormalizedEmailMessage:
    provider_message_id: str
    provider_thread_id: str
    from_address: str | None
    subject: str
    body_text: str
    received_at: datetime | None
    raw_payload: dict[str, Any]


def pull_new_messages(
    *,
    fetcher: GmailFetcher | None = None,
    since: datetime | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """Pull + normalize Gmail payloads into internal connector contracts."""
    if fetcher is None:
        logger.info("gmail_pull_stub", reason="no_fetcher")
        # TODO(v1-phase2): wire Gmail API client and incremental cursors.
        return []

    payloads = fetcher(since, max_results)
    normalized: list[dict[str, Any]] = []
    for payload in payloads:
        normalized_message = normalize_gmail_message(payload)
        normalized.append(asdict(normalized_message))
    logger.info("gmail_pull_normalized", count=len(normalized))
    return normalized


def normalize_gmail_message(payload: GmailMessagePayload) -> NormalizedEmailMessage:
    """Normalize a single Gmail API message payload into the V1 email artifact contract."""
    provider_message_id = str(payload.get("id") or "")
    provider_thread_id = str(payload.get("threadId") or "")
    if not provider_message_id or not provider_thread_id:
        raise ValueError("Gmail payload must include id and threadId")

    headers = _extract_headers(payload)
    subject = headers.get("subject") or "(no subject)"
    from_address = headers.get("from")
    body_text = str(payload.get("snippet") or "")
    # TODO(rhe-14): decode MIME parts from payload.body / payload.parts when ingest is wired.
    received_at = _parse_internal_date(payload.get("internalDate"))

    return NormalizedEmailMessage(
        provider_message_id=provider_message_id,
        provider_thread_id=provider_thread_id,
        from_address=from_address,
        subject=subject,
        body_text=body_text,
        received_at=received_at,
        raw_payload=dict(payload),
    )


def _extract_headers(payload: GmailMessagePayload) -> dict[str, str]:
    parsed_headers: dict[str, str] = {}
    header_items = payload.get("payload", {}).get("headers", [])
    if not isinstance(header_items, list):
        return parsed_headers

    for item in header_items:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "").strip().lower()
        value = str(item.get("value") or "").strip()
        if name and value:
            parsed_headers[name] = value
    return parsed_headers


def _parse_internal_date(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        timestamp_ms = int(str(value))
    except ValueError:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
