"""GoogleCalendarProvider — credential-aware Google Calendar provider for Helm.

Implements the ``CalendarProvider`` Protocol by constructing a
``google_workspace_mcp.services.calendar.CalendarService`` with a pre-built
``_service`` injected directly. The credential bypass pattern sets
``svc._service`` before the ``service`` property is ever accessed, so the
``gauth`` module inside the MCP package is never invoked.

Security contract: access_token and refresh_token are never logged.
Only user_id and event-level fields (event_id, calendar_id) appear in log events.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import structlog
from googleapiclient.discovery import build
from helm_storage.repositories.users import get_credentials
from sqlalchemy.orm import Session

from helm_providers.credentials import build_google_credentials

if TYPE_CHECKING:
    from helm_orchestration.schemas import (
        CalendarSyncRequest,
        CalendarSyncResult,
        SyncLookupRequest,
        SyncLookupResult,
    )

log = structlog.get_logger(__name__)


class GoogleCalendarProvider:
    """Google Calendar provider backed by a user's stored OAuth credentials.

    Satisfies the ``CalendarProvider`` Protocol without inheriting from it —
    Python structural typing (``Protocol``) is used for compatibility checking.
    """

    def __init__(self, user_id: int, db: Session) -> None:
        """Construct a provider for the given user.

        Loads the user's Google credentials from the DB, refreshes the token if
        necessary, and constructs a ``CalendarService`` with the API client
        injected directly. Setting ``_service`` before accessing the ``service``
        property ensures the lazy-load path (which calls into ``gauth``) is never
        triggered.

        Args:
            user_id: Internal Helm user ID.
            db: Active SQLAlchemy ``Session``.

        Raises:
            RuntimeError: If no Google credentials exist for this user.
        """
        from google_workspace_mcp.services.calendar import CalendarService

        creds = get_credentials(user_id, "google", db)
        if creds is None:
            raise RuntimeError(f"No Google credentials for user_id={user_id}")

        google_creds = build_google_credentials(user_id, creds, db)

        # Bypass CalendarService.__init__ (which calls BaseGoogleService.__init__)
        # by using __new__, then manually set the required attributes so the
        # `service` property never triggers the gauth lazy-load path.
        svc = CalendarService.__new__(CalendarService)
        svc.service_name = "calendar"
        svc.version = "v3"
        svc._service = build("calendar", "v3", credentials=google_creds)

        self._cal_svc = svc
        self._user_id = user_id

    # ------------------------------------------------------------------
    # CalendarProvider Protocol implementation
    # ------------------------------------------------------------------

    def upsert_calendar_block(self, request: CalendarSyncRequest) -> CalendarSyncResult:
        """Create or update a calendar event from a ``CalendarSyncRequest``.

        Converts the payload to a Google Calendar event body, then calls
        ``events().insert()`` for new events or ``events().update()`` for
        existing ones (identified by ``payload.external_object_id``).

        HTTP error classification:
        - 404 → TERMINAL_FAILURE (event vanished, can't update)
        - 429 → RETRYABLE_FAILURE (rate limited)
        - 5xx → RETRYABLE_FAILURE (transient server error)
        - other → TERMINAL_FAILURE

        Args:
            request: ``CalendarSyncRequest`` containing event details.

        Returns:
            ``CalendarSyncResult`` with status and (on success) ``external_object_id``.
        """
        from helm_orchestration.schemas import (
            CalendarSyncResult,
            SyncOutcomeStatus,
            SyncRetryDisposition,
        )

        try:
            payload = request.item.payload
            title = payload.get("title", "")
            description = payload.get("description", "")
            start_str = payload.get("start")
            end_str = payload.get("end")
            calendar_id = payload.get("calendar_id") or "primary"

            if not title or not start_str or not end_str:
                error_msg = "Event payload missing required fields: title, start, end"
                log.error(
                    "upsert_calendar_block_validation_error",
                    user_id=self._user_id,
                    error=error_msg,
                    payload_keys=list(payload.keys()),
                )
                return CalendarSyncResult(
                    status=SyncOutcomeStatus.TERMINAL_FAILURE,
                    retry_disposition=SyncRetryDisposition.TERMINAL,
                    error_summary=error_msg,
                )

            try:
                start_dt = self._parse_datetime(start_str)
                end_dt = self._parse_datetime(end_str)
                start_rfc3339 = self._format_rfc3339(start_dt)
                end_rfc3339 = self._format_rfc3339(end_dt)
            except ValueError as exc:
                error_msg = f"Datetime formatting error: {exc}"
                log.error(
                    "upsert_calendar_block_datetime_error",
                    user_id=self._user_id,
                    error=error_msg,
                    start=start_str,
                    end=end_str,
                )
                return CalendarSyncResult(
                    status=SyncOutcomeStatus.TERMINAL_FAILURE,
                    retry_disposition=SyncRetryDisposition.TERMINAL,
                    error_summary=error_msg,
                )

            event_body: dict[str, Any] = {
                "summary": title,
                "start": {"dateTime": start_rfc3339},
                "end": {"dateTime": end_rfc3339},
            }
            if description:
                event_body["description"] = description

            service = self._cal_svc.service
            external_object_id = payload.get("external_object_id")

            if external_object_id:
                log.info(
                    "calendar_upsert_update",
                    user_id=self._user_id,
                    event_id=external_object_id,
                    title=title,
                    start=start_rfc3339,
                    calendar_id=calendar_id,
                )
                result = service.events().update(
                    calendarId=calendar_id,
                    eventId=external_object_id,
                    body=event_body,
                ).execute()
            else:
                log.info(
                    "calendar_upsert_insert",
                    user_id=self._user_id,
                    title=title,
                    start=start_rfc3339,
                    calendar_id=calendar_id,
                )
                result = service.events().insert(
                    calendarId=calendar_id,
                    body=event_body,
                ).execute()

            returned_event_id = result.get("id")
            log.info(
                "calendar_upsert_success",
                user_id=self._user_id,
                event_id=returned_event_id,
                calendar_id=calendar_id,
                operation="update" if external_object_id else "insert",
            )

            return CalendarSyncResult(
                status=SyncOutcomeStatus.SUCCEEDED,
                retry_disposition=SyncRetryDisposition.TERMINAL,
                external_object_id=returned_event_id,
            )

        except Exception as exc:
            status_code: int | None = None
            if hasattr(exc, "resp"):
                status_code = exc.resp.status
            elif hasattr(exc, "status_code"):
                status_code = exc.status_code

            if status_code == 404:
                retry_disposition = SyncRetryDisposition.TERMINAL
                outcome_status = SyncOutcomeStatus.TERMINAL_FAILURE
            elif status_code == 429:
                retry_disposition = SyncRetryDisposition.RETRYABLE
                outcome_status = SyncOutcomeStatus.RETRYABLE_FAILURE
            elif status_code is not None and 500 <= status_code < 600:
                retry_disposition = SyncRetryDisposition.RETRYABLE
                outcome_status = SyncOutcomeStatus.RETRYABLE_FAILURE
            else:
                retry_disposition = SyncRetryDisposition.TERMINAL
                outcome_status = SyncOutcomeStatus.TERMINAL_FAILURE

            error_msg = str(exc)
            log.error(
                "calendar_upsert_failed",
                user_id=self._user_id,
                error=error_msg,
                status_code=status_code,
                retry_disposition=str(retry_disposition),
            )

            return CalendarSyncResult(
                status=outcome_status,
                retry_disposition=retry_disposition,
                error_summary=error_msg,
            )

    def reconcile_calendar_block(self, request: SyncLookupRequest) -> SyncLookupResult:
        """Retrieve a calendar event and verify it matches the stored fingerprint.

        Calls ``events().get()`` to fetch the live event, then compares a
        canonical fingerprint of its fields against ``request.payload_fingerprint``
        to detect manual edits or deletions.

        Google returns ``status='cancelled'`` for deleted events instead of 404;
        both cases are mapped to ``found=False``.

        Args:
            request: ``SyncLookupRequest`` with ``external_object_id`` and
                ``payload_fingerprint``.

        Returns:
            ``SyncLookupResult`` indicating whether the event exists and matches.
        """
        from helm_orchestration.schemas import SyncLookupResult

        if not request.external_object_id:
            error_msg = "reconcile_calendar_block requires external_object_id (Google event ID)"
            log.error(
                "reconcile_calendar_block_missing_event_id",
                user_id=self._user_id,
                error=error_msg,
                planned_item_key=request.planned_item_key,
            )
            return SyncLookupResult(
                found=False,
                payload_fingerprint_matches=None,
                details={"error": error_msg},
            )

        try:
            service = self._cal_svc.service
            log.info(
                "reconcile_calendar_block_lookup",
                user_id=self._user_id,
                event_id=request.external_object_id,
                planned_item_key=request.planned_item_key,
                calendar_id=request.calendar_id,
            )

            event = service.events().get(
                calendarId=request.calendar_id,
                eventId=request.external_object_id,
            ).execute()

            if event.get("status") == "cancelled":
                log.info(
                    "reconcile_calendar_block_event_cancelled",
                    user_id=self._user_id,
                    event_id=request.external_object_id,
                    planned_item_key=request.planned_item_key,
                )
                return SyncLookupResult(
                    found=False,
                    external_object_id=request.external_object_id,
                    payload_fingerprint_matches=None,
                    provider_state="cancelled",
                    details={"error": "Event was deleted (status=cancelled)"},
                )

            live_event_fingerprint = self._fingerprint_event(event)
            fingerprints_match = live_event_fingerprint == request.payload_fingerprint

            details: dict[str, Any] = {
                "live_event_fields": {
                    "title": event.get("summary", ""),
                    "start": event.get("start", {}).get("dateTime"),
                    "end": event.get("end", {}).get("dateTime"),
                    "description": event.get("description", ""),
                },
            }

            if not fingerprints_match:
                log.info(
                    "reconcile_calendar_block_drift_detected",
                    user_id=self._user_id,
                    planned_item_key=request.planned_item_key,
                    event_id=request.external_object_id,
                )
                details["fingerprint_mismatch"] = {
                    "stored": request.payload_fingerprint,
                    "live": live_event_fingerprint,
                }

            log.info(
                "reconcile_calendar_block_success",
                user_id=self._user_id,
                event_id=request.external_object_id,
                found=True,
                fingerprint_matches=fingerprints_match,
            )

            return SyncLookupResult(
                found=True,
                external_object_id=request.external_object_id,
                payload_fingerprint_matches=fingerprints_match,
                provider_state="found",
                details=details,
            )

        except Exception as exc:
            status_code: int | None = None
            if hasattr(exc, "resp"):
                status_code = exc.resp.status
            elif hasattr(exc, "status_code"):
                status_code = exc.status_code

            if status_code == 404:
                log.info(
                    "reconcile_calendar_block_not_found",
                    user_id=self._user_id,
                    event_id=request.external_object_id,
                    planned_item_key=request.planned_item_key,
                )
                return SyncLookupResult(
                    found=False,
                    external_object_id=request.external_object_id,
                    payload_fingerprint_matches=None,
                    provider_state="not_found",
                    details={"error": "Event not found in calendar"},
                )

            error_msg = str(exc)
            log.error(
                "reconcile_calendar_block_failed",
                user_id=self._user_id,
                error=error_msg,
                event_id=request.external_object_id,
                status_code=status_code,
            )
            return SyncLookupResult(
                found=False,
                external_object_id=request.external_object_id,
                payload_fingerprint_matches=None,
                details={"error": error_msg, "status_code": status_code},
            )

    def list_today_events(self, calendar_id: str, timezone: ZoneInfo) -> list[dict]:
        """Return today's events ordered by start time, bounded by operator local time.

        Args:
            calendar_id: Google Calendar ID (e.g. ``"primary"``).
            timezone: Operator's local timezone used to compute day boundaries.

        Returns:
            List of raw Google Calendar event dicts ordered by start time.
        """
        service = self._cal_svc.service
        now_local = datetime.now(timezone)
        start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        time_min = start_of_day.isoformat()
        time_max = end_of_day.isoformat()

        log.info(
            "list_today_events",
            user_id=self._user_id,
            calendar_id=calendar_id,
            timezone=str(timezone),
            time_min=time_min,
            time_max=time_max,
        )

        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = result.get("items", [])
        log.info(
            "list_today_events_complete",
            user_id=self._user_id,
            calendar_id=calendar_id,
            event_count=len(events),
        )
        return events

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse an RFC3339 or ISO datetime string into a timezone-aware ``datetime``.

        Args:
            dt_str: Datetime string (e.g. ``"2026-03-14T10:00:00Z"``).

        Returns:
            Timezone-aware ``datetime``.

        Raises:
            ValueError: If the string is not parseable or has no timezone.
        """
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid datetime format: {dt_str}") from exc

        if dt.tzinfo is None:
            raise ValueError(f"Datetime must include timezone information: {dt_str}")

        return dt

    def _format_rfc3339(self, dt: datetime) -> str:
        """Format a timezone-aware ``datetime`` as an RFC3339 string.

        Args:
            dt: Timezone-aware ``datetime``.

        Returns:
            RFC3339 string (e.g. ``"2026-03-14T10:00:00+00:00"``).

        Raises:
            ValueError: If ``dt`` has no timezone.
        """
        if dt.tzinfo is None:
            raise ValueError(f"Datetime must have timezone: {dt}")
        return dt.isoformat()

    def _fingerprint_event(self, event: dict[str, Any]) -> str:
        """Create a canonical JSON fingerprint of a Google Calendar event dict.

        Extracts ``summary``, ``start.dateTime``, ``end.dateTime``, and
        ``description``, normalises all datetimes to UTC (strips sub-second
        precision), and serialises as compact sorted-keys JSON.

        Normalising to UTC is required because Google returns datetimes in the
        calendar's local timezone (e.g. ``-07:00``) regardless of how they were
        stored, so a direct string comparison would produce false drift signals.

        Args:
            event: Raw event dict from ``events().get().execute()``.

        Returns:
            Canonical JSON string suitable for equality comparison.
        """

        def _normalize_dt(dt_str: str) -> str:
            if not dt_str:
                return ""
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone(UTC)
                dt = dt.replace(microsecond=0)
                return dt.isoformat()
            except ValueError:
                return dt_str

        fingerprint_data = {
            "title": event.get("summary", ""),
            "start": _normalize_dt(event.get("start", {}).get("dateTime", "")),
            "end": _normalize_dt(event.get("end", {}).get("dateTime", "")),
            "description": event.get("description", ""),
        }
        return json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":"))
