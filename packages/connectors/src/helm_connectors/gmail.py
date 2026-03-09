from __future__ import annotations

import base64
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from helm_observability.logging import get_logger

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
_GMAIL_REQUIRED_ENV_VARS = (
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
    "GMAIL_USER_EMAIL",
)

NORMALIZATION_ERROR_MISSING_ID = "missing_id"
NORMALIZATION_ERROR_INVALID_PAYLOAD = "invalid_payload"


@dataclass(slots=True, frozen=True)
class PullMessagesReport:
    messages: list[NormalizedGmailMessage]
    failure_counts: dict[str, int] = field(default_factory=dict)


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


def normalize_message_checked(
    raw_payload: Mapping[str, Any], *, normalized_at: datetime | None = None
) -> tuple[NormalizedGmailMessage | None, str | None]:
    try:
        return normalize_message(raw_payload, normalized_at=normalized_at), None
    except ValueError as exc:
        if "non-empty `id`" in str(exc):
            return None, NORMALIZATION_ERROR_MISSING_ID
        return None, NORMALIZATION_ERROR_INVALID_PAYLOAD
    except Exception:
        return None, NORMALIZATION_ERROR_INVALID_PAYLOAD


def _decode_base64url(value: str) -> str:
    padded = value + "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return decoded.decode("utf-8", errors="replace")


def _extract_headers(payload: Mapping[str, Any]) -> dict[str, str]:
    headers_raw = payload.get("headers")
    if not isinstance(headers_raw, list):
        return {}

    headers: dict[str, str] = {}
    for item in headers_raw:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name", "")).strip()
        value = str(item.get("value", "")).strip()
        if name and value:
            headers[name] = value
    return headers


def _extract_body_text(payload: Mapping[str, Any]) -> str:
    direct_body = payload.get("body")
    if isinstance(direct_body, Mapping):
        data = direct_body.get("data")
        if isinstance(data, str) and data:
            try:
                return _decode_base64url(data).strip()
            except Exception:
                return ""

    parts = payload.get("parts")
    if not isinstance(parts, list):
        return ""

    plain_candidates: list[str] = []
    html_candidates: list[str] = []
    for part in parts:
        if not isinstance(part, Mapping):
            continue
        mime_type = str(part.get("mimeType", "")).lower()
        part_text = _extract_body_text(part)
        if not part_text:
            continue
        if mime_type.startswith("text/plain"):
            plain_candidates.append(part_text)
        elif mime_type.startswith("text/html"):
            html_candidates.append(part_text)

    if plain_candidates:
        return "\n".join(plain_candidates).strip()
    if html_candidates:
        return "\n".join(html_candidates).strip()
    return ""


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise ValueError(f"Missing required environment variable: {name}")


def _build_refreshed_credentials() -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    credentials = Credentials(
        token=None,
        refresh_token=_require_env("GMAIL_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_require_env("GMAIL_CLIENT_ID"),
        client_secret=_require_env("GMAIL_CLIENT_SECRET"),
        scopes=[GMAIL_SCOPE],
    )
    credentials.refresh(Request())
    return credentials


def _build_gmail_service() -> Any:
    from googleapiclient.discovery import build

    credentials = _build_refreshed_credentials()
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _build_gmail_raw_payload(service: Any, message_id: str) -> dict[str, Any]:
    response = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    payload = response.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}
    headers = _extract_headers(payload_mapping)
    body_text = _extract_body_text(payload_mapping)
    return {
        "id": response.get("id", message_id),
        "threadId": response.get("threadId", message_id),
        "headers": headers,
        "from": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "body_text": body_text or response.get("snippet", ""),
        "snippet": response.get("snippet", ""),
        "internalDate": response.get("internalDate"),
    }


def pull_new_messages(
    manual_payload: list[dict[str, Any]] | None = None,
) -> list[NormalizedGmailMessage]:
    return pull_new_messages_report(manual_payload=manual_payload).messages


def pull_new_messages_report(
    manual_payload: list[dict[str, Any]] | None = None,
) -> PullMessagesReport:
    logger = get_logger("helm_connectors.gmail")
    failure_counts: dict[str, int] = {}

    def _add_failure(code: str) -> None:
        failure_counts[code] = failure_counts.get(code, 0) + 1

    if manual_payload is not None:
        logger.info("gmail_pull_manual_payload", count=len(manual_payload))
        messages: list[NormalizedGmailMessage] = []
        for item in manual_payload:
            normalized, failure = normalize_message_checked(item)
            if normalized is not None:
                messages.append(normalized)
                continue
            if failure is not None:
                _add_failure(failure)
        if failure_counts:
            logger.warning("gmail_pull_manual_payload_failures", failure_counts=failure_counts)
        return PullMessagesReport(messages=messages, failure_counts=failure_counts)

    missing = [name for name in _GMAIL_REQUIRED_ENV_VARS if not os.getenv(name, "").strip()]
    if missing:
        logger.info("gmail_pull_unconfigured", missing_env=missing)
        return PullMessagesReport(messages=[], failure_counts={})

    try:
        service = _build_gmail_service()
    except ImportError:
        logger.warning("gmail_pull_missing_google_dependencies")
        return PullMessagesReport(messages=[], failure_counts={})
    except Exception as exc:
        logger.warning("gmail_pull_auth_failed", error=str(exc))
        return PullMessagesReport(messages=[], failure_counts={})

    try:
        response = (
            service.users()
            .messages()
            .list(userId="me", maxResults=25, includeSpamTrash=False)
            .execute()
        )
    except Exception as exc:
        logger.warning("gmail_pull_list_failed", error=str(exc))
        return PullMessagesReport(messages=[], failure_counts={})

    message_refs = response.get("messages")
    if not isinstance(message_refs, list):
        return PullMessagesReport(messages=[], failure_counts={})

    normalized_messages: list[NormalizedGmailMessage] = []
    for item in message_refs:
        if not isinstance(item, Mapping):
            continue
        message_id = str(item.get("id", "")).strip()
        if not message_id:
            continue
        try:
            raw_payload = _build_gmail_raw_payload(service, message_id)
            normalized, failure = normalize_message_checked(raw_payload)
            if normalized is not None:
                normalized_messages.append(normalized)
            elif failure is not None:
                _add_failure(failure)
        except Exception as exc:
            logger.warning("gmail_pull_message_failed", message_id=message_id, error=str(exc))
            _add_failure(NORMALIZATION_ERROR_INVALID_PAYLOAD)

    logger.info(
        "gmail_pull_completed",
        count=len(normalized_messages),
        failure_counts=failure_counts,
    )
    return PullMessagesReport(messages=normalized_messages, failure_counts=failure_counts)
