"""End-to-end test: real Google Calendar API, real parse, real sync.

This test exercises the full weekly scheduling flow against a live Google
Calendar account. It creates events, verifies they exist, then cleans them up.

Requirements:
  HELM_E2E=true must be set (handled by conftest.py)
  HELM_CALENDAR_TEST_ID must be set to a non-"primary" staging calendar ID
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN must be set.

Run with:
  HELM_E2E=true HELM_CALENDAR_TEST_ID=<staging_id> \\
    uv run --frozen --extra dev pytest tests/e2e/test_weekly_scheduling_calendar_e2e.py -v -s

Skipped automatically when HELM_E2E is not set (conftest handles this).
Also skipped when Google credentials are not present (secondary gate).
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

from helm_connectors.google_calendar import GoogleCalendarAdapter, GoogleCalendarAuth
from helm_orchestration.schemas import (
    ApprovedSyncItem,
    CalendarSyncRequest,
    SyncLookupRequest,
    SyncOperation,
    SyncOutcomeStatus,
    SyncTargetSystem,
)
from helm_orchestration.workflow_service import _calendar_sync_fingerprint

_CREDS_PRESENT = all(
    os.getenv(v, "").strip()
    for v in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
)

pytestmark = pytest.mark.skipif(
    not _CREDS_PRESENT,
    reason="Google credentials not set (GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN)",
)


@pytest.fixture(scope="module")
def adapter() -> GoogleCalendarAdapter:
    return GoogleCalendarAdapter(GoogleCalendarAuth())


def _make_request(
    *,
    title: str,
    start: datetime,
    end: datetime,
    key: str,
) -> tuple[CalendarSyncRequest, str]:
    """Build a CalendarSyncRequest and its stored fingerprint."""
    calendar_id = os.getenv("HELM_CALENDAR_TEST_ID", "primary")
    payload = {
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "description": "",
        "calendar_id": calendar_id,
    }
    fingerprint = _calendar_sync_fingerprint(payload)
    req = CalendarSyncRequest(
        item=ApprovedSyncItem(
            proposal_artifact_id=999,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key=key,
            execution_order=1,
            payload_fingerprint=fingerprint,
            payload=payload,
        )
    )
    return req, fingerprint


class TestWeeklySchedulingCalendarE2E:
    """E2E tests that create real Google Calendar events and verify them."""

    created_event_ids: list[str]

    @pytest.fixture(autouse=True)
    def cleanup(self, adapter: GoogleCalendarAdapter) -> None:
        self.created_event_ids = []
        yield
        calendar_id = os.getenv("HELM_CALENDAR_TEST_ID", "primary")
        service = adapter._get_service()
        for event_id in self.created_event_ids:
            try:
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            except Exception:
                pass

    def test_create_single_event_and_reconcile(self, adapter: GoogleCalendarAdapter) -> None:
        """Create one event, verify it exists, verify fingerprint matches."""
        start = datetime.now(UTC) + timedelta(days=7, hours=1)
        end = start + timedelta(hours=2)

        req, fingerprint = _make_request(
            title="[Helm E2E Test] Deep work block",
            start=start,
            end=end,
            key="e2e:deep-work",
        )

        result = adapter.upsert_calendar_block(req)
        assert result.status == SyncOutcomeStatus.SUCCEEDED, f"create failed: {result.error_summary}"
        assert result.external_object_id
        self.created_event_ids.append(result.external_object_id)

        lookup = SyncLookupRequest(
            proposal_artifact_id=999,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="e2e:deep-work",
            payload_fingerprint=fingerprint,
            external_object_id=result.external_object_id,
            calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary"),
        )
        reconcile = adapter.reconcile_calendar_block(lookup)
        assert reconcile.found is True
        assert reconcile.payload_fingerprint_matches is True, (
            f"False drift: {reconcile.details.get('fingerprint_mismatch')}"
        )

    def test_create_three_events_weekly_schedule(self, adapter: GoogleCalendarAdapter) -> None:
        """Simulate a full weekly schedule: 3 events across Mon/Tue/Wed."""
        today = datetime.now(UTC)
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)

        blocks = [
            ("[Helm E2E] Monday deep work", next_monday + timedelta(hours=10), 120),
            ("[Helm E2E] Tuesday team sync", next_monday + timedelta(days=1, hours=14), 60),
            ("[Helm E2E] Wednesday focus block", next_monday + timedelta(days=2, hours=9), 120),
        ]

        results = []
        fingerprints = []
        for title, start, duration_min in blocks:
            end = start + timedelta(minutes=duration_min)
            req, fp = _make_request(title=title, start=start, end=end, key=f"e2e:{title[11:31]}")
            result = adapter.upsert_calendar_block(req)
            assert result.status == SyncOutcomeStatus.SUCCEEDED, f"create failed for {title!r}: {result.error_summary}"
            self.created_event_ids.append(result.external_object_id)
            results.append(result)
            fingerprints.append(fp)

        assert len(results) == 3

        for (title, _, _), result, fp in zip(blocks, results, fingerprints):
            lookup = SyncLookupRequest(
                proposal_artifact_id=999,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key=f"e2e:{title[11:31]}",
                payload_fingerprint=fp,
                external_object_id=result.external_object_id,
                calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary"),
            )
            reconcile = adapter.reconcile_calendar_block(lookup)
            assert reconcile.found is True, f"Event not found for {title!r}"
            assert reconcile.payload_fingerprint_matches is True, (
                f"False drift for {title!r}: {reconcile.details.get('fingerprint_mismatch')}"
            )

    def test_drift_detected_after_manual_edit(self, adapter: GoogleCalendarAdapter) -> None:
        """Create an event, patch it out-of-band, verify drift is detected."""
        start = datetime.now(UTC) + timedelta(days=7, hours=3)
        end = start + timedelta(hours=1)

        req, fingerprint = _make_request(
            title="[Helm E2E Test] Drift target",
            start=start,
            end=end,
            key="e2e:drift-target",
        )

        result = adapter.upsert_calendar_block(req)
        assert result.status == SyncOutcomeStatus.SUCCEEDED
        event_id = result.external_object_id
        self.created_event_ids.append(event_id)

        calendar_id = os.getenv("HELM_CALENDAR_TEST_ID", "primary")
        adapter._get_service().events().patch(
            calendarId=calendar_id,
            eventId=event_id,
            body={"summary": "[Helm E2E Test] Drift target (MANUALLY EDITED)"},
        ).execute()

        lookup = SyncLookupRequest(
            proposal_artifact_id=999,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="e2e:drift-target",
            payload_fingerprint=fingerprint,
            external_object_id=event_id,
            calendar_id=calendar_id,
        )
        reconcile = adapter.reconcile_calendar_block(lookup)
        assert reconcile.found is True
        assert reconcile.payload_fingerprint_matches is False, "Expected drift to be detected"
        assert reconcile.details["live_event_fields"]["title"] == (
            "[Helm E2E Test] Drift target (MANUALLY EDITED)"
        )

    def test_deleted_event_returns_not_found(self, adapter: GoogleCalendarAdapter) -> None:
        """Create an event, delete it out-of-band, verify reconcile returns found=False."""
        start = datetime.now(UTC) + timedelta(days=7, hours=5)
        end = start + timedelta(hours=1)

        req, fingerprint = _make_request(
            title="[Helm E2E Test] Delete me",
            start=start,
            end=end,
            key="e2e:delete-me",
        )

        result = adapter.upsert_calendar_block(req)
        assert result.status == SyncOutcomeStatus.SUCCEEDED
        event_id = result.external_object_id

        calendar_id = os.getenv("HELM_CALENDAR_TEST_ID", "primary")
        # Delete directly — not in cleanup list
        adapter._get_service().events().delete(calendarId=calendar_id, eventId=event_id).execute()

        lookup = SyncLookupRequest(
            proposal_artifact_id=999,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="e2e:delete-me",
            payload_fingerprint=fingerprint,
            external_object_id=event_id,
            calendar_id=calendar_id,
        )
        reconcile = adapter.reconcile_calendar_block(lookup)
        assert reconcile.found is False
