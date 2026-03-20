"""GoogleCalendarProvider — credential-aware Google Calendar provider for Helm.

Wraps ``google_workspace_mcp.services.calendar.CalendarService`` with
per-user DB-backed OAuth credentials. All calendar operations delegate
to CalendarService methods — no direct googleapiclient calls.

Credentials are built from ``UserCredentialsORM`` and injected into
``CalendarService._service`` before any method is called, bypassing
the gauth env-var lazy-load path.

Security contract: access_token and refresh_token are never logged.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import structlog
from google_workspace_mcp.services.calendar import CalendarService
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
    """Google Calendar provider backed by a user's stored OAuth credentials."""

    def __init__(self, user_id: int, db: Session) -> None:
        creds = get_credentials(user_id, "google", db)
        if creds is None:
            raise RuntimeError(f"No Google credentials for user_id={user_id}")

        google_creds = build_google_credentials(user_id, creds, db)

        svc = CalendarService()
        svc._service = build("calendar", "v3", credentials=google_creds)

        self._cal_svc = svc
        self._user_id = user_id

    # ------------------------------------------------------------------
    # CalendarProvider Protocol implementation
    # ------------------------------------------------------------------

    def upsert_calendar_block(self, request: CalendarSyncRequest) -> CalendarSyncResult:
        from helm_orchestration.schemas import (
            CalendarSyncResult,
            SyncOutcomeStatus,
            SyncRetryDisposition,
        )

        payload = request.item.payload
        title = payload.get("title", "")
        description = payload.get("description", "") or None
        start_str = payload.get("start")
        end_str = payload.get("end")
        calendar_id = payload.get("calendar_id") or "primary"
        external_object_id = payload.get("external_object_id")

        if not title or not start_str or not end_str:
            error_msg = "Event payload missing required fields: title, start, end"
            log.error("upsert_calendar_block_validation_error", user_id=self._user_id, error=error_msg)
            return CalendarSyncResult(
                status=SyncOutcomeStatus.TERMINAL_FAILURE,
                retry_disposition=SyncRetryDisposition.TERMINAL,
                error_summary=error_msg,
            )

        if external_object_id:
            log.info("calendar_upsert_update", user_id=self._user_id, event_id=external_object_id, title=title, calendar_id=calendar_id)
            self._cal_svc.delete_event(event_id=external_object_id, send_notifications=False)

        log.info("calendar_upsert_insert", user_id=self._user_id, title=title, start=start_str, calendar_id=calendar_id)
        result = self._cal_svc.create_event(
            summary=title,
            start_time=start_str,
            end_time=end_str,
            description=description,
            calendar_id=calendar_id,
            send_notifications=False,
        )

        if not result or result.get("error"):
            status_code = result.get("status_code") if result else None
            error_msg = result.get("message", "create_event failed") if result else "create_event returned None"
            log.error("calendar_upsert_failed", user_id=self._user_id, error=error_msg, status_code=status_code)
            if status_code == 429:
                return CalendarSyncResult(status=SyncOutcomeStatus.RETRYABLE_FAILURE, retry_disposition=SyncRetryDisposition.RETRYABLE, error_summary=error_msg)
            if status_code is not None and 500 <= status_code < 600:
                return CalendarSyncResult(status=SyncOutcomeStatus.RETRYABLE_FAILURE, retry_disposition=SyncRetryDisposition.RETRYABLE, error_summary=error_msg)
            return CalendarSyncResult(status=SyncOutcomeStatus.TERMINAL_FAILURE, retry_disposition=SyncRetryDisposition.TERMINAL, error_summary=error_msg)

        returned_event_id = result.get("id")
        log.info("calendar_upsert_success", user_id=self._user_id, event_id=returned_event_id, calendar_id=calendar_id, operation="update" if external_object_id else "insert")
        return CalendarSyncResult(
            status=SyncOutcomeStatus.SUCCEEDED,
            retry_disposition=SyncRetryDisposition.TERMINAL,
            external_object_id=returned_event_id,
        )

    def reconcile_calendar_block(self, request: SyncLookupRequest) -> SyncLookupResult:
        from helm_orchestration.schemas import SyncLookupResult

        if not request.external_object_id:
            return SyncLookupResult(found=False, payload_fingerprint_matches=None, details={"error": "reconcile_calendar_block requires external_object_id"})

        log.info("reconcile_calendar_block_lookup", user_id=self._user_id, event_id=request.external_object_id, calendar_id=request.calendar_id)
        event = self._cal_svc.get_event_details(event_id=request.external_object_id, calendar_id=request.calendar_id)

        if event is None:
            log.info("reconcile_calendar_block_not_found", user_id=self._user_id, event_id=request.external_object_id)
            return SyncLookupResult(found=False, external_object_id=request.external_object_id, payload_fingerprint_matches=None, provider_state="not_found", details={"error": "Event not found in calendar"})

        if event.get("error"):
            # get_event_details returns an error dict on failure (handle_api_error pattern)
            status_code = event.get("status_code")
            if status_code == 404:
                return SyncLookupResult(found=False, external_object_id=request.external_object_id, payload_fingerprint_matches=None, provider_state="not_found", details={"error": "Event not found in calendar"})
            log.error("reconcile_calendar_block_failed", user_id=self._user_id, error=event.get("message"))
            return SyncLookupResult(found=False, external_object_id=request.external_object_id, payload_fingerprint_matches=None, details={"error": event.get("message")})

        if event.get("status") == "cancelled":
            return SyncLookupResult(found=False, external_object_id=request.external_object_id, payload_fingerprint_matches=None, provider_state="cancelled", details={"error": "Event was deleted (status=cancelled)"})

        live_fingerprint = _fingerprint_event(event)
        matches = live_fingerprint == request.payload_fingerprint
        if not matches:
            log.info("reconcile_calendar_block_drift_detected", user_id=self._user_id, event_id=request.external_object_id)

        log.info("reconcile_calendar_block_success", user_id=self._user_id, event_id=request.external_object_id, fingerprint_matches=matches)
        return SyncLookupResult(
            found=True,
            external_object_id=request.external_object_id,
            payload_fingerprint_matches=matches,
            provider_state="found",
            details={"live_event_fields": {"title": event.get("summary", ""), "start": event.get("start", {}).get("dateTime"), "end": event.get("end", {}).get("dateTime"), "description": event.get("description", "")}},
        )

    def list_today_events(self, calendar_id: str, timezone: ZoneInfo) -> list[dict]:
        now_local = datetime.now(timezone)
        start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        log.info("list_today_events", user_id=self._user_id, calendar_id=calendar_id, timezone=str(timezone))
        events = self._cal_svc.get_events(
            calendar_id=calendar_id,
            time_min=start_of_day.isoformat(),
            time_max=end_of_day.isoformat(),
        )
        log.info("list_today_events_complete", user_id=self._user_id, event_count=len(events))
        return events

    def find_free_slot(
        self,
        calendar_id: str,
        date: datetime,
        duration_minutes: int,
        tz: ZoneInfo,
        *,
        search_start_hour: int = 9,
        search_end_hour: int = 18,
        step_minutes: int = 30,
    ) -> datetime:
        """Find the first free slot on ``date`` of at least ``duration_minutes``."""
        local_date = date.astimezone(tz) if date.tzinfo else date.replace(tzinfo=tz)
        day_start = local_date.replace(hour=search_start_hour, minute=0, second=0, microsecond=0)
        day_end = local_date.replace(hour=search_end_hour, minute=0, second=0, microsecond=0)

        events = self._cal_svc.get_events(
            calendar_id=calendar_id,
            time_min=day_start.isoformat(),
            time_max=day_end.isoformat(),
        )

        busy: list[tuple[datetime, datetime]] = []
        for ev in events:
            start_str = ev.get("start", {}).get("dateTime")
            end_str = ev.get("end", {}).get("dateTime")
            if start_str and end_str:
                try:
                    b_start = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(UTC)
                    b_end = datetime.fromisoformat(end_str.replace("Z", "+00:00")).astimezone(UTC)
                    busy.append((b_start, b_end))
                except ValueError:
                    continue

        duration = timedelta(minutes=duration_minutes)
        step = timedelta(minutes=step_minutes)
        candidate = day_start
        while candidate + duration <= day_end:
            c_utc = candidate.astimezone(UTC)
            c_end_utc = (candidate + duration).astimezone(UTC)
            if not any(b_start < c_end_utc and b_end > c_utc for b_start, b_end in busy):
                return candidate
            candidate += step

        log.warning("find_free_slot_no_gap_found", user_id=self._user_id, calendar_id=calendar_id, date=local_date.date().isoformat(), duration_minutes=duration_minutes)
        return day_start


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _fingerprint_event(event: dict[str, Any]) -> str:
    """Canonical JSON fingerprint of a Google Calendar event for drift detection."""

    def _norm_dt(dt_str: str) -> str:
        if not dt_str:
            return ""
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC)
            return dt.replace(microsecond=0).isoformat()
        except ValueError:
            return dt_str

    return json.dumps(
        {
            "title": event.get("summary", ""),
            "start": _norm_dt(event.get("start", {}).get("dateTime", "")),
            "end": _norm_dt(event.get("end", {}).get("dateTime", "")),
            "description": event.get("description", ""),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
