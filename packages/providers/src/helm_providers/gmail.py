"""GmailProvider — credential-aware Gmail provider for Helm.

Wraps ``google_workspace_mcp.services.gmail.GmailService`` with per-user
DB-backed OAuth credentials.  Credentials are built from ``UserCredentialsORM``
and injected into ``GmailService._service`` before any method is called,
bypassing the gauth env-var lazy-load path.

``send_reply`` delegates to ``GmailService.create_reply``.
Gmail history-cursor polling (``pull_new_messages_report``,
``pull_changed_messages_report``) is implemented here because the MCP has
no incremental sync equivalent.

Security contract: access_token, refresh_token, and client_secret are never
logged.  Only user_id appears in structured log events.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from google_workspace_mcp.services.gmail import GmailService
from googleapiclient.discovery import build
from helm_storage.repositories.users import get_credentials
from sqlalchemy.orm import Session

from helm_providers.credentials import build_google_credentials

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NORMALIZATION_ERROR_MISSING_ID = "missing_id"
NORMALIZATION_ERROR_INVALID_PAYLOAD = "invalid_payload"


# ---------------------------------------------------------------------------
# Data classes (identical shapes to helm_connectors.gmail)
# ---------------------------------------------------------------------------


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


@dataclass(slots=True, frozen=True)
class PullMessagesReport:
    messages: list[NormalizedGmailMessage]
    failure_counts: dict[str, int] = field(default_factory=dict)
    next_history_cursor: str | None = None
    mode: str = "poll"
    recovery_reason: str | None = None


@dataclass(slots=True, frozen=True)
class GmailSendResult:
    provider_message_id: str
    provider_thread_id: str
    from_address: str
    to_address: str
    subject: str
    body_text: str
    sent_at: datetime
    source: str = "gmail"


class GmailSendError(Exception):
    def __init__(
        self,
        failure_class: str,
        message: str,
        *,
        provider_error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_class = failure_class
        self.provider_error_code = provider_error_code


# ---------------------------------------------------------------------------
# Normalization helpers (transplanted verbatim from helm_connectors.gmail)
# ---------------------------------------------------------------------------


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


def _http_status(exc: Exception) -> int | None:
    response = getattr(exc, "resp", None)
    status = getattr(response, "status", None)
    return status if isinstance(status, int) else None


def _raise_send_error(exc: Exception) -> None:
    status = _http_status(exc)
    message = str(exc)
    message_lower = message.lower()
    if status == 429:
        raise GmailSendError("rate_limited", message, provider_error_code="429") from exc
    if status is not None and 500 <= status <= 599:
        raise GmailSendError("provider_5xx", message, provider_error_code=str(status)) from exc
    if status in {401, 403}:
        raise GmailSendError("auth_error", message, provider_error_code=str(status)) from exc
    if status is not None and 400 <= status <= 499:
        failure_class = "invalid_payload"
        if "recipient" in message_lower or "invalid to" in message_lower:
            failure_class = "invalid_recipient"
        raise GmailSendError(failure_class, message, provider_error_code=str(status)) from exc
    raise GmailSendError("unknown_delivery_state", message) from exc


# ---------------------------------------------------------------------------
# Private Gmail API helpers (module-level for consistent patching in tests)
# ---------------------------------------------------------------------------


def _build_gmail_raw_payload(service: Any, message_id: str) -> dict[str, Any]:
    response = service.users().messages().get(userId="me", id=message_id, format="full").execute()
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


def _normalize_manual_payload(
    manual_payload: list[dict[str, Any]],
    *,
    logger: Any,
    next_history_cursor: str | None,
    mode: str,
) -> PullMessagesReport:
    failure_counts: dict[str, int] = {}

    def _add_failure(code: str) -> None:
        failure_counts[code] = failure_counts.get(code, 0) + 1

    logger.info("gmail_pull_manual_payload", count=len(manual_payload), mode=mode)
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
    return PullMessagesReport(
        messages=messages,
        failure_counts=failure_counts,
        next_history_cursor=next_history_cursor,
        mode=mode,
    )


def _get_current_history_cursor(service: Any) -> str | None:
    try:
        response = service.users().getProfile(userId="me").execute()
    except Exception:
        return None
    history_id = response.get("historyId")
    if history_id is None:
        return None
    history_value = str(history_id).strip()
    return history_value or None


def _normalize_message_ids(
    service: Any,
    *,
    message_ids: list[str],
    logger: Any,
    next_history_cursor: str | None,
    mode: str,
) -> PullMessagesReport:
    failure_counts: dict[str, int] = {}
    normalized_messages: list[NormalizedGmailMessage] = []

    def _add_failure(code: str) -> None:
        failure_counts[code] = failure_counts.get(code, 0) + 1

    for message_id in message_ids:
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
        mode=mode,
        next_history_cursor=next_history_cursor,
    )
    return PullMessagesReport(
        messages=normalized_messages,
        failure_counts=failure_counts,
        next_history_cursor=next_history_cursor,
        mode=mode,
    )


def _history_recovery_reason(exc: Exception) -> str:
    status = _http_status(exc)
    message = str(exc).lower()
    if status == 404 or "starthistoryid" in message or "historyid" in message:
        return "history_cursor_invalid"
    return "history_pull_failed"


def _list_recent_message_ids(service: Any) -> list[str]:
    response = (
        service.users()
        .messages()
        .list(userId="me", maxResults=25, includeSpamTrash=False)
        .execute()
    )
    message_refs = response.get("messages")
    if not isinstance(message_refs, list):
        return []

    message_ids: list[str] = []
    for item in message_refs:
        if not isinstance(item, Mapping):
            continue
        message_id = str(item.get("id", "")).strip()
        if message_id:
            message_ids.append(message_id)
    return message_ids


def _list_changed_message_ids(
    service: Any,
    *,
    start_history_cursor: str,
) -> tuple[list[str], str | None]:
    seen: set[str] = set()
    message_ids: list[str] = []
    next_history_cursor = start_history_cursor
    page_token: str | None = None

    while True:
        request = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_cursor,
                historyTypes=["messageAdded"],
                maxResults=100,
                pageToken=page_token,
            )
        )
        response = request.execute()
        history_id = response.get("historyId")
        if history_id is not None:
            next_history_cursor = str(history_id).strip() or next_history_cursor

        history_entries = response.get("history")
        if isinstance(history_entries, list):
            for entry in history_entries:
                if not isinstance(entry, Mapping):
                    continue
                messages_added = entry.get("messagesAdded")
                if not isinstance(messages_added, list):
                    continue
                for item in messages_added:
                    if not isinstance(item, Mapping):
                        continue
                    message = item.get("message")
                    if not isinstance(message, Mapping):
                        continue
                    message_id = str(message.get("id", "")).strip()
                    if not message_id or message_id in seen:
                        continue
                    seen.add(message_id)
                    message_ids.append(message_id)

        page_token_value = response.get("nextPageToken")
        if page_token_value is None:
            page_token = None
        else:
            page_token = str(page_token_value).strip() or None
        if page_token is None:
            break

    return message_ids, next_history_cursor


# ---------------------------------------------------------------------------
# GmailProvider
# ---------------------------------------------------------------------------


class GmailProvider:
    """Gmail provider backed by a user's stored OAuth credentials.

    Satisfies the ``InboxProvider`` Protocol without inheriting from it.
    Credentials are loaded from the DB; the sender address is read from
    ``creds.email`` (not from the ``GMAIL_USER_EMAIL`` environment variable),
    making this provider multi-user ready.
    """

    def __init__(self, user_id: int, db: Session) -> None:
        creds = get_credentials(user_id, "google", db)
        if creds is None:
            raise RuntimeError(f"No Google credentials for user_id={user_id}")

        google_creds = build_google_credentials(user_id, creds, db)

        svc = GmailService()
        svc._service = build("gmail", "v1", credentials=google_creds)

        self._gmail_svc = svc
        self._user_id = user_id
        self._sender_email: str = str(creds.email or "")

    # ------------------------------------------------------------------
    # InboxProvider Protocol implementation
    # ------------------------------------------------------------------

    def pull_new_messages_report(
        self,
        manual_payload: list[dict] | None = None,
    ) -> PullMessagesReport:
        """Fetch and normalise new messages, returning a structured report.

        If ``manual_payload`` is provided, messages are normalised directly from
        that list without calling the Gmail API.

        Args:
            manual_payload: Optional list of pre-fetched raw message dicts.

        Returns:
            ``PullMessagesReport`` with normalised messages and metadata.
        """
        logger = log.bind(user_id=self._user_id)
        service = self._gmail_svc.service

        if manual_payload is not None:
            return _normalize_manual_payload(
                manual_payload,
                logger=logger,
                next_history_cursor=None,
                mode="manual",
            )

        try:
            message_ids = _list_recent_message_ids(service)
        except Exception as exc:
            logger.warning("gmail_pull_list_failed", error=str(exc))
            return PullMessagesReport(messages=[], failure_counts={}, mode="poll")

        return _normalize_message_ids(
            service,
            message_ids=message_ids,
            logger=logger,
            next_history_cursor=_get_current_history_cursor(service),
            mode="poll",
        )

    def pull_changed_messages_report(
        self,
        *,
        last_history_cursor: str | None,
        manual_payload: list[dict] | None = None,
    ) -> PullMessagesReport:
        """Fetch messages changed since ``last_history_cursor``.

        Falls back to a full new-messages pull when ``last_history_cursor`` is
        ``None`` (bootstrap case).  Also falls back on history pull failure,
        capturing the recovery reason in the returned report.

        Args:
            last_history_cursor: Opaque Gmail history ID from a previous call.
            manual_payload: Optional pre-fetched raw message dicts.

        Returns:
            ``PullMessagesReport`` with mode and optional recovery_reason set.
        """
        logger = log.bind(user_id=self._user_id)
        service = self._gmail_svc.service

        if manual_payload is not None:
            return _normalize_manual_payload(
                manual_payload,
                logger=logger,
                next_history_cursor=last_history_cursor,
                mode="manual",
            )

        if last_history_cursor is None:
            logger.info("gmail_history_bootstrap_poll")
            poll_report = self.pull_new_messages_report()
            return PullMessagesReport(
                messages=poll_report.messages,
                failure_counts=poll_report.failure_counts,
                next_history_cursor=poll_report.next_history_cursor,
                mode="bootstrap",
                recovery_reason="missing_history_cursor",
            )

        try:
            message_ids, next_history_cursor = _list_changed_message_ids(
                service,
                start_history_cursor=last_history_cursor,
            )
        except Exception as exc:
            recovery_reason = _history_recovery_reason(exc)
            logger.warning(
                "gmail_history_pull_failed",
                error=str(exc),
                last_history_cursor=last_history_cursor,
                recovery_reason=recovery_reason,
            )
            poll_report = self.pull_new_messages_report()
            return PullMessagesReport(
                messages=poll_report.messages,
                failure_counts=poll_report.failure_counts,
                next_history_cursor=poll_report.next_history_cursor,
                mode="recovery_poll",
                recovery_reason=recovery_reason,
            )

        if next_history_cursor == last_history_cursor:
            current_history_cursor = _get_current_history_cursor(service)
            if current_history_cursor is not None:
                next_history_cursor = current_history_cursor

        return _normalize_message_ids(
            service,
            message_ids=message_ids,
            logger=logger,
            next_history_cursor=next_history_cursor,
            mode="history",
        )

    def send_reply(
        self,
        *,
        provider_thread_id: str,
        to_address: str,
        subject: str,
        body_text: str,
    ) -> GmailSendResult:
        """Send a reply within an existing provider thread.

        Validates ``to_address`` and ``body_text`` before attempting the send.
        Raises ``GmailSendError`` on validation failure or API error.
        """
        logger = log.bind(user_id=self._user_id)

        to_address = to_address.strip()
        if not to_address:
            raise GmailSendError("invalid_recipient", "Reply recipient is required.")
        if not body_text.strip():
            raise GmailSendError("invalid_payload", "Reply body is required.")

        # Construct the original_message dict that GmailService.create_reply expects
        original_message = {
            "from": to_address,
            "subject": subject,
            "threadId": provider_thread_id,
        }

        try:
            response = self._gmail_svc.create_reply(
                original_message=original_message,
                reply_body=body_text,
                send=True,
            )
        except TimeoutError as exc:
            raise GmailSendError("timeout", "Gmail send timed out.") from exc
        except ConnectionError as exc:
            raise GmailSendError("connection_error", "Gmail send connection failed.") from exc
        except Exception as exc:
            _raise_send_error(exc)

        if not response or response.get("error"):
            raise GmailSendError("unknown_delivery_state", f"Gmail send failed: {response}")

        provider_message_id = str(response.get("id", "")).strip()
        if not provider_message_id:
            raise GmailSendError(
                "unknown_delivery_state",
                "Gmail send did not return a provider message id.",
            )
        returned_thread_id = str(response.get("threadId", provider_thread_id)).strip() or provider_thread_id

        logger.info(
            "gmail_send_completed",
            to_address=to_address,
            provider_message_id=provider_message_id,
            provider_thread_id=returned_thread_id,
        )

        return GmailSendResult(
            provider_message_id=provider_message_id,
            provider_thread_id=returned_thread_id,
            from_address=self._sender_email,
            to_address=to_address,
            subject=subject,
            body_text=body_text,
            sent_at=datetime.now(tz=UTC),
        )
