from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from helm_observability.logging import get_logger

NORMALIZATION_ERROR_MISSING_ID = "missing_id"
NORMALIZATION_ERROR_INVALID_PAYLOAD = "invalid_payload"


@dataclass(slots=True, frozen=True)
class NormalizedLinkedInMessage:
    provider_message_id: str
    provider_thread_id: str
    sender_name: str
    body_text: str
    received_at: datetime
    normalized_at: datetime
    source: str = "linkedin"


@dataclass(slots=True, frozen=True)
class PullEventsReport:
    events: list[NormalizedLinkedInMessage]
    failure_counts: dict[str, int] = field(default_factory=dict)


def _parse_received_at(value: Any, *, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return fallback
    return fallback


def normalize_event(
    raw_payload: Mapping[str, Any], *, normalized_at: datetime | None = None
) -> NormalizedLinkedInMessage:
    now = normalized_at or datetime.now(tz=UTC)
    provider_message_id = str(
        raw_payload.get("id") or raw_payload.get("provider_message_id") or ""
    ).strip()
    if not provider_message_id:
        raise ValueError("LinkedIn payload must include non-empty `id`.")

    provider_thread_id = str(
        raw_payload.get("thread_id")
        or raw_payload.get("threadId")
        or raw_payload.get("conversation_id")
        or provider_message_id
    ).strip()
    sender_name = str(raw_payload.get("sender_name") or raw_payload.get("sender") or "").strip()
    body_text = str(raw_payload.get("body_text") or raw_payload.get("text") or "").strip()
    received_at = _parse_received_at(raw_payload.get("received_at"), fallback=now)

    return NormalizedLinkedInMessage(
        provider_message_id=provider_message_id,
        provider_thread_id=provider_thread_id or provider_message_id,
        sender_name=sender_name,
        body_text=body_text,
        received_at=received_at,
        normalized_at=now,
    )


def normalize_event_checked(
    raw_payload: Mapping[str, Any], *, normalized_at: datetime | None = None
) -> tuple[NormalizedLinkedInMessage | None, str | None]:
    try:
        return normalize_event(raw_payload, normalized_at=normalized_at), None
    except ValueError as exc:
        if "non-empty `id`" in str(exc):
            return None, NORMALIZATION_ERROR_MISSING_ID
        return None, NORMALIZATION_ERROR_INVALID_PAYLOAD
    except Exception:
        return None, NORMALIZATION_ERROR_INVALID_PAYLOAD


def pull_new_events(
    manual_payload: list[dict[str, Any]] | None = None,
) -> list[NormalizedLinkedInMessage]:
    return pull_new_events_report(manual_payload=manual_payload).events


def pull_new_events_report(
    manual_payload: list[dict[str, Any]] | None = None,
) -> PullEventsReport:
    logger = get_logger("helm_connectors.linkedin")
    failure_counts: dict[str, int] = {}

    def _add_failure(code: str) -> None:
        failure_counts[code] = failure_counts.get(code, 0) + 1

    if manual_payload is not None:
        logger.info("linkedin_pull_manual_payload", count=len(manual_payload))
        normalized_events: list[NormalizedLinkedInMessage] = []
        for item in manual_payload:
            normalized, failure = normalize_event_checked(item)
            if normalized is not None:
                normalized_events.append(normalized)
                continue
            if failure is not None:
                _add_failure(failure)
        if failure_counts:
            logger.warning("linkedin_pull_manual_payload_failures", failure_counts=failure_counts)
        return PullEventsReport(events=normalized_events, failure_counts=failure_counts)

    logger.info("linkedin_pull_stub_manual_mode")
    # TODO(v1-linkedin-feasibility): select ingestion path (official API vs defer).
    # TODO(v1-linkedin-go-no-go): enable only when criteria in
    # docs/internal/linkedin-feasibility-v1.md are met.
    return PullEventsReport(events=[], failure_counts={})
