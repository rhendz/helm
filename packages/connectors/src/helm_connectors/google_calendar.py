from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from helm_observability.logging import get_logger

if TYPE_CHECKING:
    from helm_orchestration.schemas import (
        CalendarSyncRequest,
        CalendarSyncResult,
        SyncLookupRequest,
        SyncLookupResult,
    )

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
_CALENDAR_REQUIRED_ENV_VARS = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
)

logger = get_logger("helm_connectors.google_calendar")


def _require_env(name: str) -> str:
    """Extract and validate a required environment variable.
    
    Args:
        name: Environment variable name.
        
    Returns:
        The environment variable value (stripped).
        
    Raises:
        ValueError: If the environment variable is missing or empty.
    """
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise ValueError(f"Missing required environment variable: {name}")


class GoogleCalendarAuth:
    """Manages OAuth2 credentials for Google Calendar API access.
    
    Handles credential initialization from environment variables and
    transparent token refresh for long-lived API operations.
    """

    def __init__(self) -> None:
        """Initialize OAuth2 credentials from environment variables.
        
        Reads CALENDAR_CLIENT_ID, CALENDAR_CLIENT_SECRET, and CALENDAR_REFRESH_TOKEN
        from environment. Initializes a Credentials object with these values but
        does not refresh the token immediately—refresh happens on first API call.
        
        Raises:
            ValueError: If any required environment variable is missing.
        """
        try:
            self._client_id = _require_env("GOOGLE_CLIENT_ID")
            self._client_secret = _require_env("GOOGLE_CLIENT_SECRET")
            self._refresh_token = _require_env("GOOGLE_REFRESH_TOKEN")
        except ValueError as exc:
            logger.error("calendar_auth_init_failed", error=str(exc))
            raise

        # Initialize credentials object (token is None; will be refreshed before use)
        self._credentials = self._build_credentials()
        logger.info("calendar_auth_initialized", client_id=self._client_id)

    def _build_credentials(self) -> Any:
        """Build an unrefreshed Credentials object from stored env vars.
        
        Returns:
            A google.oauth2.credentials.Credentials instance with refresh_token set,
            but token field set to None (not yet refreshed).
        """
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=None,  # No access token yet; will be obtained on refresh
            refresh_token=self._refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=[CALENDAR_SCOPE],
        )

    def get_refreshed_credentials(self) -> Any:
        """Get refreshed OAuth2 credentials for API calls.
        
        Calls refresh(Request()) to obtain a fresh access_token if the
        current one is expired or missing. Logs the refresh attempt and
        any errors that occur.
        
        Returns:
            A google.oauth2.credentials.Credentials instance with a valid
            access_token ready for API use.
            
        Raises:
            ValueError: If credential refresh fails with auth errors (401, 403).
            RuntimeError: If credential refresh fails due to network or server errors.
        """
        try:
            from google.auth.transport.requests import Request

            logger.info(
                "calendar_credential_refresh_attempt",
                client_id=self._client_id,
                expired=self._credentials.expired if hasattr(self._credentials, "expired") else None,
            )
            self._credentials.refresh(Request())
            logger.info("calendar_credential_refreshed", client_id=self._client_id)
            return self._credentials
        except ValueError as exc:
            # Typically: invalid_grant, expired refresh_token
            error_msg = f"Calendar credential refresh failed (invalid grant or expired token): {exc}"
            logger.error("calendar_credential_refresh_failed", error=str(exc), error_class="auth_error")
            raise ValueError(error_msg) from exc
        except Exception as exc:
            # Network errors, 5xx responses, or other runtime errors
            error_msg = f"Calendar credential refresh failed: {exc}"
            logger.error(
                "calendar_credential_refresh_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise RuntimeError(error_msg) from exc


class GoogleCalendarAdapter:
    """Real Google Calendar API adapter implementing CalendarSystemAdapter protocol.
    
    Handles creating and updating events on Google Calendar using OAuth credentials.
    """

    def __init__(self, auth: GoogleCalendarAuth) -> None:
        """Initialize adapter with GoogleCalendarAuth instance.
        
        Args:
            auth: GoogleCalendarAuth instance with valid credentials.
        """
        self._auth = auth
        self._service: Any = None

    def _get_service(self) -> Any:
        """Get or create Google Calendar API service instance.
        
        Returns:
            A googleapiclient.discovery.Resource instance for Calendar API.
        """
        if self._service is None:
            from googleapiclient.discovery import build

            credentials = self._auth.get_refreshed_credentials()
            self._service = build("calendar", "v3", credentials=credentials)
        return self._service

    def upsert_calendar_block(self, request: CalendarSyncRequest) -> CalendarSyncResult:
        """Create or update a calendar event.
        
        Converts CalendarSyncRequest to Google Calendar event body, handles
        datetime formatting, and calls either events().insert() for new events
        or events().update() for existing events.
        
        Args:
            request: CalendarSyncRequest containing event details and external_object_id.
            
        Returns:
            CalendarSyncResult with Google event ID, status, and retry disposition.
        """
        from helm_orchestration.schemas import (
            CalendarSyncResult,
            SyncOutcomeStatus,
            SyncRetryDisposition,
        )

        try:
            # Extract event details from payload
            payload = request.item.payload
            title = payload.get("title", "")
            description = payload.get("description", "")
            start_str = payload.get("start")
            end_str = payload.get("end")
            calendar_id = payload.get("calendar_id") or "primary"

            # Validate required fields
            if not title or not start_str or not end_str:
                error_msg = "Event payload missing required fields: title, start, end"
                logger.error(
                    "upsert_calendar_block_validation_error",
                    error=error_msg,
                    payload_keys=list(payload.keys()),
                )
                return CalendarSyncResult(
                    status=SyncOutcomeStatus.TERMINAL_FAILURE,
                    retry_disposition=SyncRetryDisposition.TERMINAL,
                    error_summary=error_msg,
                )

            # Parse and format datetimes
            try:
                start_dt = self._parse_datetime(start_str)
                end_dt = self._parse_datetime(end_str)
                start_rfc3339 = self._format_rfc3339(start_dt)
                end_rfc3339 = self._format_rfc3339(end_dt)
            except ValueError as exc:
                error_msg = f"Datetime formatting error: {exc}"
                logger.error(
                    "upsert_calendar_block_datetime_error",
                    error=error_msg,
                    start=start_str,
                    end=end_str,
                )
                return CalendarSyncResult(
                    status=SyncOutcomeStatus.TERMINAL_FAILURE,
                    retry_disposition=SyncRetryDisposition.TERMINAL,
                    error_summary=error_msg,
                )

            # Build event body
            event_body = {
                "summary": title,
                "start": {"dateTime": start_rfc3339},
                "end": {"dateTime": end_rfc3339},
            }
            if description:
                event_body["description"] = description

            # Call appropriate API method based on external_object_id
            service = self._get_service()
            # External object ID comes from the payload, not the item itself
            # (ApprovedSyncItem doesn't have external_object_id; that's in sync records)
            external_object_id = payload.get("external_object_id")

            if external_object_id:
                # Update existing event
                logger.info(
                    "upsert_calendar_block: calling events.update",
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
                # Create new event
                logger.info(
                    "upsert_calendar_block: calling events.insert",
                    title=title,
                    start=start_rfc3339,
                    calendar_id=calendar_id,
                )
                result = service.events().insert(
                    calendarId=calendar_id,
                    body=event_body,
                ).execute()

            returned_event_id = result.get("id")
            logger.info(
                "upsert_calendar_block_success",
                event_id=returned_event_id,
                calendar_id=calendar_id,
                operation="update" if external_object_id else "create",
            )

            return CalendarSyncResult(
                status=SyncOutcomeStatus.SUCCEEDED,
                retry_disposition=SyncRetryDisposition.TERMINAL,
                external_object_id=returned_event_id,
            )

        except Exception as exc:
            # Classify HTTP errors
            status_code: int | None = None
            if hasattr(exc, "resp"):
                status_code = exc.resp.status
            elif hasattr(exc, "status_code"):
                status_code = exc.status_code

            if status_code == 404:
                # Event not found (trying to update non-existent event)
                retry_disposition = SyncRetryDisposition.TERMINAL
                outcome_status = SyncOutcomeStatus.TERMINAL_FAILURE
            elif status_code == 429:
                # Rate limited
                retry_disposition = SyncRetryDisposition.RETRYABLE
                outcome_status = SyncOutcomeStatus.RETRYABLE_FAILURE
            elif status_code and 500 <= status_code < 600:
                # Server error
                retry_disposition = SyncRetryDisposition.RETRYABLE
                outcome_status = SyncOutcomeStatus.RETRYABLE_FAILURE
            else:
                # Unknown error
                retry_disposition = SyncRetryDisposition.TERMINAL
                outcome_status = SyncOutcomeStatus.TERMINAL_FAILURE

            error_msg = str(exc)
            logger.error(
                "upsert_calendar_block_failed",
                error=error_msg,
                status_code=status_code,
                retry_disposition=str(retry_disposition),
            )

            return CalendarSyncResult(
                status=outcome_status,
                retry_disposition=retry_disposition,
                error_summary=error_msg,
            )

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string (RFC3339 or ISO format) to datetime object.
        
        Args:
            dt_str: Datetime string in RFC3339 or ISO format.
            
        Returns:
            datetime object with tzinfo set.
            
        Raises:
            ValueError: If datetime string is invalid or has no timezone.
        """
        try:
            # Try parsing as RFC3339 / ISO format
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid datetime format: {dt_str}") from exc

        if dt.tzinfo is None:
            raise ValueError(f"Datetime must include timezone information: {dt_str}")

        return dt

    def _format_rfc3339(self, dt: datetime) -> str:
        """Format datetime object as RFC3339 string with timezone.
        
        Args:
            dt: datetime object with tzinfo.
            
        Returns:
            RFC3339 formatted string (e.g., "2026-03-14T10:00:00-07:00").
            
        Raises:
            ValueError: If datetime has no timezone.
        """
        if dt.tzinfo is None:
            raise ValueError(f"Datetime must have timezone: {dt}")
        return dt.isoformat()

    def reconcile_calendar_block(self, request: SyncLookupRequest) -> SyncLookupResult:
        """Retrieve a calendar event and verify it matches the planned state.
        
        Calls events().get() to retrieve the live event by its Google event ID,
        extracts relevant fields (title, start, end, description), canonicalizes
        to JSON, and compares against the stored payload_fingerprint to detect
        manual edits or deletions.
        
        Args:
            request: SyncLookupRequest containing external_object_id (Google event ID)
                    and payload_fingerprint (stored canonical JSON of planned event).
                    
        Returns:
            SyncLookupResult with:
            - found=True/False (event exists in calendar)
            - payload_fingerprint_matches=True/False (live event matches planned state)
            - details containing live_event_fields (title, start, end, description)
              and fingerprint_mismatch_fields if drift detected.
        """
        from helm_orchestration.schemas import SyncLookupResult

        if not request.external_object_id:
            error_msg = "reconcile_calendar_block requires external_object_id (Google event ID)"
            logger.error(
                "reconcile_calendar_block_missing_event_id",
                error=error_msg,
                planned_item_key=request.planned_item_key,
            )
            return SyncLookupResult(
                found=False,
                payload_fingerprint_matches=None,
                details={"error": error_msg},
            )

        try:
            service = self._get_service()
            logger.info(
                "reconcile_calendar_block: calling events.get",
                eventId=request.external_object_id,
                planned_item_key=request.planned_item_key,
                calendar_id=request.calendar_id,
            )

            # Retrieve the live event from calendar
            event = service.events().get(
                calendarId=request.calendar_id,
                eventId=request.external_object_id,
            ).execute()

            # Google returns status='cancelled' for deleted events instead of 404
            if event.get("status") == "cancelled":
                logger.info(
                    "reconcile_calendar_block_event_cancelled",
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

            # Extract and canonicalize live event state
            live_event_fingerprint = self._fingerprint_event(event)
            stored_fingerprint = request.payload_fingerprint

            # Determine if event matches planned state
            fingerprints_match = live_event_fingerprint == stored_fingerprint

            # Prepare details for drift analysis
            details = {
                "live_event_fields": {
                    "title": event.get("summary", ""),
                    "start": event.get("start", {}).get("dateTime"),
                    "end": event.get("end", {}).get("dateTime"),
                    "description": event.get("description", ""),
                },
            }

            if not fingerprints_match:
                # Log drift details for investigation
                logger.info(
                    "drift_detected",
                    planned_item_key=request.planned_item_key,
                    event_id=request.external_object_id,
                    stored_fingerprint=stored_fingerprint,
                    live_fingerprint=live_event_fingerprint,
                )
                details["fingerprint_mismatch"] = {
                    "stored": stored_fingerprint,
                    "live": live_event_fingerprint,
                }

            logger.info(
                "reconcile_calendar_block_success",
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
            # Check if event not found (404)
            status_code: int | None = None
            if hasattr(exc, "resp"):
                status_code = exc.resp.status
            elif hasattr(exc, "status_code"):
                status_code = exc.status_code

            if status_code == 404:
                logger.info(
                    "reconcile_calendar_block_event_not_found",
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

            # Unexpected error
            error_msg = str(exc)
            logger.error(
                "reconcile_calendar_block_failed",
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
        """Return today's events from the calendar in operator local time.

        Args:
            calendar_id: Google Calendar ID (e.g. "primary").
            timezone: Operator's local timezone for determining day boundaries.

        Returns:
            List of Google Calendar event dicts ordered by start time.
        """
        service = self._get_service()
        now_local = datetime.now(timezone)
        start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        time_min = start_of_day.isoformat()
        time_max = end_of_day.isoformat()

        logger.info(
            "list_today_events",
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
        logger.info(
            "list_today_events_complete",
            calendar_id=calendar_id,
            event_count=len(events),
        )
        return events

    def _fingerprint_event(self, event: dict[str, Any]) -> str:
        """Create a canonical JSON fingerprint of a calendar event.

        Extracts title, start.dateTime, end.dateTime, and description from
        the event and normalizes datetimes to UTC ISO format. This matches
        the format produced by _calendar_sync_fingerprint in the workflow,
        enabling direct comparison for drift detection.

        Google Calendar returns datetimes with the calendar's local timezone
        offset (e.g. -07:00) regardless of how they were stored. Normalizing
        to UTC ensures fingerprints match across timezones.

        Args:
            event: Google Calendar event dict (result from events().get().execute()).

        Returns:
            Canonical JSON string (sorted keys) representing event state in UTC.
        """
        from datetime import timezone as _tz

        def _normalize_dt(dt_str: str) -> str:
            if not dt_str:
                return ""
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone(_tz.utc)
                # Truncate to seconds — Google strips sub-second precision on round-trip
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
        # Canonical JSON: sorted keys, no whitespace, for deterministic comparison
        return json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":"))
