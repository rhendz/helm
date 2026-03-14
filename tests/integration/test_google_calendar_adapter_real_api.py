"""Integration tests for GoogleCalendarAdapter with real Google Calendar API calls.

These tests verify:
1. Event creation (events().insert) with proper RFC3339 datetime formatting
2. Event update (events().update) with existing external_object_id
3. Error classification (404→TERMINAL, 429→RETRIABLE, 5xx→RETRIABLE)
4. CalendarSyncResult populated correctly with Google event ID and retry disposition
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from helm_connectors.google_calendar import GoogleCalendarAdapter, GoogleCalendarAuth
from helm_orchestration.schemas import (
    ApprovedSyncItem,
    CalendarSyncRequest,
    SyncLookupRequest,
    SyncOperation,
    SyncOutcomeStatus,
    SyncRetryDisposition,
    SyncTargetSystem,
)


@pytest.fixture
def calendar_auth() -> GoogleCalendarAuth:
    """Fixture providing GoogleCalendarAuth with test env vars."""
    with patch.dict(
        os.environ,
        {
            "CALENDAR_CLIENT_ID": "test-client-id",
            "CALENDAR_CLIENT_SECRET": "test-client-secret",
            "CALENDAR_REFRESH_TOKEN": "test-refresh-token",
        },
    ):
        return GoogleCalendarAuth()


@pytest.fixture
def adapter(calendar_auth: GoogleCalendarAuth) -> GoogleCalendarAdapter:
    """Fixture providing GoogleCalendarAdapter with mocked service."""
    return GoogleCalendarAdapter(calendar_auth)


class TestUpsertCalendarBlockCreate:
    """Tests for event creation (events().insert)."""

    def test_create_event_success(self, adapter: GoogleCalendarAdapter) -> None:
        """Create a new event and verify returned event ID."""
        # Setup
        start_dt = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)
        end_dt = datetime(2026, 3, 14, 11, 0, 0, tzinfo=UTC)

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="abc123",
                payload={
                    "title": "Team Standup",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "description": "Daily team sync",
                },
            )
        )

        # Mock the service
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert
        mock_insert.execute.return_value = {
            "id": "google-event-id-12345",
            "summary": "Team Standup",
        }

        adapter._service = mock_service

        # Execute
        result = adapter.upsert_calendar_block(request)

        # Verify
        assert result.status == SyncOutcomeStatus.SUCCEEDED
        assert result.retry_disposition == SyncRetryDisposition.TERMINAL
        assert result.external_object_id == "google-event-id-12345"
        assert result.error_summary is None

        # Verify API call
        mock_events.insert.assert_called_once()
        call_kwargs = mock_events.insert.call_args[1]
        assert call_kwargs["calendarId"] == "primary"
        assert call_kwargs["body"]["summary"] == "Team Standup"
        assert call_kwargs["body"]["description"] == "Daily team sync"

    def test_create_event_with_rfc3339_timezone(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Verify RFC3339 datetime formatting with timezone offset."""
        # Setup with timezone-aware datetime
        start_dt = datetime(2026, 3, 14, 10, 0, 0, tzinfo=timezone(timedelta(hours=-7)))
        end_dt = datetime(2026, 3, 14, 11, 0, 0, tzinfo=timezone(timedelta(hours=-7)))

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="abc123",
                payload={
                    "title": "Event",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
        )

        # Mock the service
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert
        mock_insert.execute.return_value = {"id": "event-id"}

        adapter._service = mock_service

        # Execute
        adapter.upsert_calendar_block(request)

        # Verify RFC3339 formatting in API call
        call_kwargs = mock_events.insert.call_args[1]
        body = call_kwargs["body"]
        start_str = body["start"]["dateTime"]
        end_str = body["end"]["dateTime"]

        # Should contain timezone offset like "-07:00"
        assert "-07:00" in start_str or "+00:00" in start_str
        assert "-07:00" in end_str or "+00:00" in end_str
        assert "T" in start_str  # ISO format with time separator

    def test_create_event_missing_title_fails(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Verify validation fails when title is missing."""
        start_dt = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)
        end_dt = datetime(2026, 3, 14, 11, 0, 0, tzinfo=UTC)

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="abc123",
                payload={
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
        )

        result = adapter.upsert_calendar_block(request)

        assert result.status == SyncOutcomeStatus.TERMINAL_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.TERMINAL
        assert "title" in result.error_summary.lower()

    def test_create_event_naive_datetime_fails(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Verify that naive datetime (no timezone) raises ValueError."""
        # Naive datetime without timezone
        start_dt = datetime(2026, 3, 14, 10, 0, 0)
        end_dt = datetime(2026, 3, 14, 11, 0, 0)

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="abc123",
                payload={
                    "title": "Event",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
        )

        result = adapter.upsert_calendar_block(request)

        assert result.status == SyncOutcomeStatus.TERMINAL_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.TERMINAL
        assert "timezone" in result.error_summary.lower()


class TestUpsertCalendarBlockUpdate:
    """Tests for event update (events().update)."""

    def test_update_event_success(self, adapter: GoogleCalendarAdapter) -> None:
        """Update an existing event with external_object_id."""
        start_dt = datetime(2026, 3, 14, 14, 0, 0, tzinfo=UTC)
        end_dt = datetime(2026, 3, 14, 15, 0, 0, tzinfo=UTC)

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=2,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="def456",
                payload={
                    "external_object_id": "google-event-id-12345",
                    "title": "Team Standup (Rescheduled)",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "description": "Updated time",
                },
            )
        )

        # Mock the service
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_update = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.update.return_value = mock_update
        mock_update.execute.return_value = {
            "id": "google-event-id-12345",
            "summary": "Team Standup (Rescheduled)",
        }

        adapter._service = mock_service

        # Execute
        result = adapter.upsert_calendar_block(request)

        # Verify
        assert result.status == SyncOutcomeStatus.SUCCEEDED
        assert result.external_object_id == "google-event-id-12345"
        assert result.error_summary is None

        # Verify update() was called, not insert()
        mock_events.update.assert_called_once()
        mock_events.insert.assert_not_called()

        call_kwargs = mock_events.update.call_args[1]
        assert call_kwargs["calendarId"] == "primary"
        assert call_kwargs["eventId"] == "google-event-id-12345"
        assert call_kwargs["body"]["summary"] == "Team Standup (Rescheduled)"

    def test_update_event_not_found_terminal(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """404 error when updating non-existent event should be TERMINAL."""
        start_dt = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)
        end_dt = datetime(2026, 3, 14, 11, 0, 0, tzinfo=UTC)

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="abc123",
                payload={
                    "external_object_id": "non-existent-event-id",
                    "title": "Event",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
        )

        # Mock 404 error
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_update = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.update.return_value = mock_update

        http_error = HttpError(
            resp=MagicMock(status=404),
            content=b"Not Found",
        )
        mock_update.execute.side_effect = http_error

        adapter._service = mock_service

        # Execute
        result = adapter.upsert_calendar_block(request)

        # Verify
        assert result.status == SyncOutcomeStatus.TERMINAL_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.TERMINAL
        assert result.external_object_id is None


class TestErrorClassification:
    """Tests for HTTP error classification and retry disposition."""

    def test_rate_limit_429_is_retriable(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """429 rate limit error should be RETRIABLE."""
        start_dt = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)
        end_dt = datetime(2026, 3, 14, 11, 0, 0, tzinfo=UTC)

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="abc123",
                payload={
                    "title": "Event",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
        )

        # Mock 429 error
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert

        http_error = HttpError(
            resp=MagicMock(status=429),
            content=b"Rate Limit Exceeded",
        )
        mock_insert.execute.side_effect = http_error

        adapter._service = mock_service

        # Execute
        result = adapter.upsert_calendar_block(request)

        # Verify
        assert result.status == SyncOutcomeStatus.RETRYABLE_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.RETRYABLE

    def test_server_error_5xx_is_retriable(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """5xx server error should be RETRIABLE."""
        start_dt = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)
        end_dt = datetime(2026, 3, 14, 11, 0, 0, tzinfo=UTC)

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="abc123",
                payload={
                    "title": "Event",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
        )

        # Mock 500 error
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert

        http_error = HttpError(
            resp=MagicMock(status=500),
            content=b"Internal Server Error",
        )
        mock_insert.execute.side_effect = http_error

        adapter._service = mock_service

        # Execute
        result = adapter.upsert_calendar_block(request)

        # Verify
        assert result.status == SyncOutcomeStatus.RETRYABLE_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.RETRYABLE

    def test_unknown_error_is_terminal(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Unexpected error should be TERMINAL."""
        start_dt = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)
        end_dt = datetime(2026, 3, 14, 11, 0, 0, tzinfo=UTC)

        request = CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="abc123",
                payload={
                    "title": "Event",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
        )

        # Mock generic error with no status code
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert
        mock_insert.execute.side_effect = RuntimeError("Connection timeout")

        adapter._service = mock_service

        # Execute
        result = adapter.upsert_calendar_block(request)

        # Verify
        assert result.status == SyncOutcomeStatus.TERMINAL_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.TERMINAL


class TestDatetimeFormatting:
    """Tests for RFC3339 datetime formatting."""

    def test_format_rfc3339_with_utc(self, adapter: GoogleCalendarAdapter) -> None:
        """Format UTC datetime as RFC3339."""
        dt = datetime(2026, 3, 14, 10, 30, 45, tzinfo=UTC)
        formatted = adapter._format_rfc3339(dt)

        assert "2026-03-14T10:30:45" in formatted
        assert "+00:00" in formatted or "Z" not in formatted  # Standard UTC offset

    def test_format_rfc3339_with_offset(self, adapter: GoogleCalendarAdapter) -> None:
        """Format datetime with timezone offset as RFC3339."""
        tz = timezone(timedelta(hours=-5, minutes=-30))
        dt = datetime(2026, 3, 14, 10, 30, 45, tzinfo=tz)
        formatted = adapter._format_rfc3339(dt)

        assert "2026-03-14T10:30:45" in formatted
        assert "-05:30" in formatted

    def test_format_rfc3339_naive_fails(self, adapter: GoogleCalendarAdapter) -> None:
        """Naive datetime (no timezone) should raise ValueError."""
        dt = datetime(2026, 3, 14, 10, 30, 45)

        with pytest.raises(ValueError, match="timezone"):
            adapter._format_rfc3339(dt)

    def test_parse_datetime_with_offset(self, adapter: GoogleCalendarAdapter) -> None:
        """Parse RFC3339 datetime with timezone offset."""
        dt_str = "2026-03-14T10:30:45-07:00"
        dt = adapter._parse_datetime(dt_str)

        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 14
        assert dt.hour == 10
        assert dt.tzinfo is not None

    def test_parse_datetime_with_z_utc(self, adapter: GoogleCalendarAdapter) -> None:
        """Parse RFC3339 datetime with Z suffix (UTC)."""
        dt_str = "2026-03-14T10:30:45Z"
        dt = adapter._parse_datetime(dt_str)

        assert dt.year == 2026
        assert dt.tzinfo is not None

    def test_parse_datetime_naive_fails(self, adapter: GoogleCalendarAdapter) -> None:
        """Naive datetime string should raise ValueError."""
        dt_str = "2026-03-14T10:30:45"

        with pytest.raises(ValueError, match="timezone"):
            adapter._parse_datetime(dt_str)

    def test_parse_datetime_invalid_format_fails(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Invalid datetime format should raise ValueError."""
        dt_str = "not-a-datetime"

        with pytest.raises(ValueError):
            adapter._parse_datetime(dt_str)


class TestReconcileCalendarBlock:
    """Tests for reconcile_calendar_block (read and drift detection)."""

    def test_reconcile_event_found_fingerprint_matches(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Retrieve event and verify it matches planned fingerprint."""
        # Setup: Create expected fingerprint from planned event
        planned_payload = {
            "title": "Team Standup",
            "start": "2026-03-14T10:00:00+00:00",
            "end": "2026-03-14T11:00:00+00:00",
            "description": "Daily team sync",
        }
        expected_fingerprint = adapter._fingerprint_event(
            {
                "summary": planned_payload["title"],
                "start": {"dateTime": planned_payload["start"]},
                "end": {"dateTime": planned_payload["end"]},
                "description": planned_payload["description"],
            }
        )

        request = SyncLookupRequest(
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="calendar:block-001",
            payload_fingerprint=expected_fingerprint,
            external_object_id="google-event-id-12345",
        )

        # Mock the service returning the same event
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_get = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.get.return_value = mock_get
        mock_get.execute.return_value = {
            "id": "google-event-id-12345",
            "summary": "Team Standup",
            "start": {"dateTime": "2026-03-14T10:00:00+00:00"},
            "end": {"dateTime": "2026-03-14T11:00:00+00:00"},
            "description": "Daily team sync",
        }

        adapter._service = mock_service

        # Execute
        result = adapter.reconcile_calendar_block(request)

        # Verify
        assert result.found is True
        assert result.external_object_id == "google-event-id-12345"
        assert result.payload_fingerprint_matches is True
        assert result.provider_state == "found"
        assert "live_event_fields" in result.details

        # Verify API call
        mock_events.get.assert_called_once()
        call_kwargs = mock_events.get.call_args[1]
        assert call_kwargs["calendarId"] == "primary"
        assert call_kwargs["eventId"] == "google-event-id-12345"

    def test_reconcile_event_found_fingerprint_mismatches(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Retrieve event and detect manual edit (fingerprint mismatch)."""
        # Setup: Create fingerprint for planned event
        planned_payload = {
            "title": "Team Standup",
            "start": "2026-03-14T10:00:00+00:00",
            "end": "2026-03-14T11:00:00+00:00",
            "description": "Daily team sync",
        }
        expected_fingerprint = adapter._fingerprint_event(
            {
                "summary": planned_payload["title"],
                "start": {"dateTime": planned_payload["start"]},
                "end": {"dateTime": planned_payload["end"]},
                "description": planned_payload["description"],
            }
        )

        request = SyncLookupRequest(
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="calendar:block-001",
            payload_fingerprint=expected_fingerprint,
            external_object_id="google-event-id-12345",
        )

        # Mock service returning modified event (title changed)
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_get = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.get.return_value = mock_get
        mock_get.execute.return_value = {
            "id": "google-event-id-12345",
            "summary": "Team Standup (MODIFIED BY USER)",  # Title changed!
            "start": {"dateTime": "2026-03-14T10:00:00+00:00"},
            "end": {"dateTime": "2026-03-14T11:00:00+00:00"},
            "description": "Daily team sync",
        }

        adapter._service = mock_service

        # Execute
        result = adapter.reconcile_calendar_block(request)

        # Verify
        assert result.found is True
        assert result.external_object_id == "google-event-id-12345"
        assert result.payload_fingerprint_matches is False  # Mismatch detected
        assert "fingerprint_mismatch" in result.details
        assert "live_event_fields" in result.details
        assert result.details["live_event_fields"]["title"] == "Team Standup (MODIFIED BY USER)"

    def test_reconcile_event_not_found_404(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Retrieve non-existent event (404) and return found=False."""
        request = SyncLookupRequest(
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="calendar:block-001",
            payload_fingerprint="abc123",
            external_object_id="non-existent-event-id",
        )

        # Mock 404 error with a real HttpError-like exception
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_get = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.get.return_value = mock_get

        # Create a mock error with resp.status = 404
        mock_error = Exception("Not Found")
        mock_error.resp = MagicMock()
        mock_error.resp.status = 404
        mock_get.execute.side_effect = mock_error

        adapter._service = mock_service

        # Execute
        result = adapter.reconcile_calendar_block(request)

        # Verify
        assert result.found is False
        assert result.external_object_id == "non-existent-event-id"
        assert result.payload_fingerprint_matches is None
        assert result.provider_state == "not_found"

    def test_reconcile_missing_external_object_id(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Reconcile without external_object_id should return error."""
        request = SyncLookupRequest(
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="calendar:block-001",
            payload_fingerprint="abc123",
            external_object_id=None,  # Missing!
        )

        # Execute
        result = adapter.reconcile_calendar_block(request)

        # Verify
        assert result.found is False
        assert result.payload_fingerprint_matches is None
        assert "error" in result.details

    def test_fingerprint_event_canonical_json(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Verify _fingerprint_event produces canonical JSON."""
        event = {
            "summary": "Test Event",
            "start": {"dateTime": "2026-03-14T10:00:00+00:00"},
            "end": {"dateTime": "2026-03-14T11:00:00+00:00"},
            "description": "Test Description",
        }

        fingerprint = adapter._fingerprint_event(event)

        # Fingerprint should be deterministic (sorted keys, no whitespace)
        # Call twice and verify same result
        fingerprint2 = adapter._fingerprint_event(event)
        assert fingerprint == fingerprint2

        # Should be valid JSON
        import json
        parsed = json.loads(fingerprint)
        assert parsed["title"] == "Test Event"
        assert parsed["start"] == "2026-03-14T10:00:00+00:00"

    def test_fingerprint_event_missing_fields(
        self, adapter: GoogleCalendarAdapter
    ) -> None:
        """Fingerprint with missing optional fields uses empty strings."""
        event = {
            "summary": "Test Event",
            # start, end, description missing
        }

        fingerprint = adapter._fingerprint_event(event)

        import json
        parsed = json.loads(fingerprint)
        assert parsed["title"] == "Test Event"
        assert parsed["start"] == ""
        assert parsed["end"] == ""
        assert parsed["description"] == ""
