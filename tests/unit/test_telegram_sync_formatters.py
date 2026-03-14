"""Unit tests for Telegram sync event formatters.

Tests cover happy path, edge cases (missing fields, malformed data), truncation,
and Telegram message size limits.
"""

from datetime import datetime

from helm_telegram_bot.formatters.sync_events import (
    format_drift_event,
    format_sync_record,
    format_sync_timeline,
)


class TestFormatSyncRecord:
    """Tests for format_sync_record function."""

    def test_happy_path_succeeded(self):
        """Test formatting a successful sync record."""
        record = {
            "sync_record_id": 1,
            "planned_item_key": "task:Weekly meeting",
            "status": "succeeded",
            "external_object_id": "evt_123abc",
            "created_at": datetime(2024, 1, 15, 2, 35, 10),
            "last_error_summary": None,
            "drift_event": None,
        }
        result = format_sync_record(record)
        assert result.startswith("✓")
        assert "Weekly meeting" in result
        assert "evt_123abc" in result
        assert "02:35:10" in result

    def test_happy_path_drift_detected(self):
        """Test formatting a record with drift detected."""
        record = {
            "sync_record_id": 2,
            "planned_item_key": "event:Planning session",
            "status": "drift_detected",
            "external_object_id": "cal_456def",
            "created_at": datetime(2024, 1, 15, 3, 45, 20),
            "last_error_summary": None,
            "drift_event": {"event_id": 1, "details": {"field_diffs": {}}},
        }
        result = format_sync_record(record)
        assert result.startswith("⚠")
        assert "Planning session" in result
        assert "cal_456def" in result

    def test_happy_path_failed(self):
        """Test formatting a failed sync record."""
        record = {
            "sync_record_id": 3,
            "planned_item_key": "task:Broken task",
            "status": "failed",
            "external_object_id": "tsk_789ghi",
            "created_at": datetime(2024, 1, 15, 4, 0, 0),
            "last_error_summary": "Connection timeout",
            "drift_event": None,
        }
        result = format_sync_record(record)
        assert result.startswith("✗")
        assert "Broken task" in result

    def test_happy_path_unknown_status(self):
        """Test formatting with unknown status uses hourglass symbol."""
        record = {
            "sync_record_id": 4,
            "planned_item_key": "task:Pending task",
            "status": "pending",
            "external_object_id": "tsk_pending",
            "created_at": datetime(2024, 1, 15, 5, 0, 0),
            "last_error_summary": None,
            "drift_event": None,
        }
        result = format_sync_record(record)
        assert result.startswith("⏳")

    def test_missing_planned_item_key(self):
        """Test handling missing planned_item_key."""
        record = {
            "sync_record_id": 5,
            "planned_item_key": "",
            "status": "succeeded",
            "external_object_id": "ext_999",
            "created_at": datetime(2024, 1, 15, 6, 0, 0),
            "last_error_summary": None,
            "drift_event": None,
        }
        result = format_sync_record(record)
        assert "ext_999" in result
        # Should fall back to external_object_id or unknown item

    def test_missing_external_object_id(self):
        """Test handling missing external_object_id."""
        record = {
            "sync_record_id": 6,
            "planned_item_key": "task:Test",
            "status": "succeeded",
            "external_object_id": None,
            "created_at": datetime(2024, 1, 15, 7, 0, 0),
            "last_error_summary": None,
            "drift_event": None,
        }
        result = format_sync_record(record)
        assert "Test" in result
        assert "unknown" in result

    def test_long_title_truncation(self):
        """Test that long titles are truncated to 40 chars."""
        long_title = "a" * 50  # 50 chars
        record = {
            "sync_record_id": 7,
            "planned_item_key": f"task:{long_title}",
            "status": "succeeded",
            "external_object_id": "ext_001",
            "created_at": datetime(2024, 1, 15, 8, 0, 0),
            "last_error_summary": None,
            "drift_event": None,
        }
        result = format_sync_record(record)
        # Title part should be truncated with ellipsis
        assert "..." in result
        # Should not contain full 50-char title
        assert long_title not in result

    def test_missing_created_at(self):
        """Test handling missing created_at timestamp."""
        record = {
            "sync_record_id": 8,
            "planned_item_key": "task:No time",
            "status": "succeeded",
            "external_object_id": "ext_002",
            "created_at": None,
            "last_error_summary": None,
            "drift_event": None,
        }
        result = format_sync_record(record)
        assert "n/a" in result or "No time" in result
        # Should not crash

    def test_malformed_created_at(self):
        """Test handling malformed created_at value."""
        record = {
            "sync_record_id": 9,
            "planned_item_key": "task:Bad time",
            "status": "succeeded",
            "external_object_id": "ext_003",
            "created_at": "invalid-timestamp",
            "last_error_summary": None,
            "drift_event": None,
        }
        result = format_sync_record(record)
        # Should not crash and should contain some timestamp
        assert "✓" in result


class TestFormatDriftEvent:
    """Tests for format_drift_event function."""

    def test_happy_path_single_field_diff(self):
        """Test formatting a drift event with a single field change."""
        event = {
            "event_id": 1,
            "summary": "Event rescheduled",
            "details": {"field_diffs": {"start": {"before": "10:00", "after": "14:00"}}},
            "created_at": datetime(2024, 1, 15, 10, 0, 0),
        }
        sync_record = {"planned_item_key": "event:Planning session"}
        result = format_drift_event(event, sync_record)
        assert "Planning session" in result
        assert "start" in result
        assert "10:00" in result
        assert "14:00" in result

    def test_happy_path_multiple_field_diffs(self):
        """Test formatting a drift event with multiple field changes."""
        event = {
            "event_id": 2,
            "summary": "Event updated",
            "details": {
                "field_diffs": {
                    "start": {"before": "09:00", "after": "10:00"},
                    "end": {"before": "17:00", "after": "18:00"},
                    "location": {"before": "Office", "after": "Remote"},
                }
            },
            "created_at": datetime(2024, 1, 15, 11, 0, 0),
        }
        sync_record = {"planned_item_key": "event:Team meeting"}
        result = format_drift_event(event, sync_record)
        assert "Team meeting" in result
        assert "start" in result
        assert "end" in result
        assert "location" in result
        assert result.count("\n") >= 3  # Multiple lines

    def test_empty_field_diffs(self):
        """Test handling empty field_diffs."""
        event = {
            "event_id": 3,
            "summary": "Event drifted",
            "details": {"field_diffs": {}},
            "created_at": datetime(2024, 1, 15, 12, 0, 0),
        }
        sync_record = {"planned_item_key": "event:Empty event"}
        result = format_drift_event(event, sync_record)
        assert "Empty event" in result
        assert "no changes" in result.lower()

    def test_missing_details(self):
        """Test handling missing details field."""
        event = {
            "event_id": 4,
            "summary": "Event drifted",
            "details": None,
            "created_at": datetime(2024, 1, 15, 13, 0, 0),
        }
        sync_record = {"planned_item_key": "event:No details"}
        result = format_drift_event(event, sync_record)
        # Should not crash
        assert "drifted" in result.lower()

    def test_malformed_field_diffs(self):
        """Test handling malformed field_diffs (not a dict)."""
        event = {
            "event_id": 5,
            "summary": "Event drifted",
            "details": {"field_diffs": "not-a-dict"},
            "created_at": datetime(2024, 1, 15, 14, 0, 0),
        }
        sync_record = {"planned_item_key": "event:Malformed"}
        result = format_drift_event(event, sync_record)
        # Should handle gracefully and note logs
        assert "Malformed" in result or "drifted" in result.lower()

    def test_missing_planned_item_key_in_sync_record(self):
        """Test handling missing planned_item_key in sync record."""
        event = {
            "event_id": 6,
            "summary": "Event drifted",
            "details": {"field_diffs": {"title": {"before": "Old", "after": "New"}}},
            "created_at": datetime(2024, 1, 15, 15, 0, 0),
        }
        sync_record = {"planned_item_key": ""}
        result = format_drift_event(event, sync_record)
        # Should still format without crashing
        assert "title" in result
        assert "Old" in result


class TestFormatSyncTimeline:
    """Tests for format_sync_timeline function."""

    def test_happy_path_multiple_records(self):
        """Test formatting a timeline with multiple sync records."""
        records = [
            {
                "sync_record_id": 1,
                "planned_item_key": "task:First task",
                "status": "succeeded",
                "external_object_id": "tsk_001",
                "created_at": datetime(2024, 1, 15, 1, 0, 0),
                "last_error_summary": None,
                "drift_event": None,
            },
            {
                "sync_record_id": 2,
                "planned_item_key": "event:Second event",
                "status": "drift_detected",
                "external_object_id": "evt_002",
                "created_at": datetime(2024, 1, 15, 2, 0, 0),
                "last_error_summary": None,
                "drift_event": {
                    "event_id": 1,
                    "summary": "Rescheduled",
                    "details": {"field_diffs": {"start": {"before": "10:00", "after": "11:00"}}},
                    "created_at": datetime(2024, 1, 15, 2, 0, 0),
                },
            },
        ]
        result = format_sync_timeline(records)
        assert "✓" in result
        assert "⚠" in result
        assert "First task" in result
        assert "Second event" in result
        assert result.count("\n") >= 2  # Multiple lines

    def test_empty_records(self):
        """Test formatting empty timeline."""
        result = format_sync_timeline([])
        assert result == ""

    def test_max_events_limit(self):
        """Test that max_events parameter limits output."""
        records = [
            {
                "sync_record_id": i,
                "planned_item_key": f"task:Task {i}",
                "status": "succeeded",
                "external_object_id": f"tsk_{i:03d}",
                "created_at": datetime(2024, 1, 15, i, 0, 0),
                "last_error_summary": None,
                "drift_event": None,
            }
            for i in range(1, 11)  # 10 records
        ]
        result = format_sync_timeline(records, max_events=3)
        # Should only show 3 records
        assert "Task 1" in result or "Task 8" in result  # First record or high-numbered
        # Should indicate more events
        assert "..." in result or "more" in result.lower()

    def test_truncation_large_timeline(self):
        """Test that large timelines are truncated to respect Telegram message limit."""
        # Create many records with long content to exceed 3800 chars
        records = [
            {
                "sync_record_id": i,
                "planned_item_key": f"task:{'A' * 50}_{i}",
                "status": "succeeded",
                "external_object_id": f"tsk_{i:03d}",
                "created_at": datetime(2024, 1, 15, (i % 23), 0, 0),  # Wrap hour to 0-23
                "last_error_summary": None,
                "drift_event": None,
            }
            for i in range(1, 30)  # 30 records with long titles
        ]
        result = format_sync_timeline(records, max_events=25)
        # Result should be under the Telegram limit
        assert len(result) <= 4096  # Telegram hard limit
        # Should indicate truncation
        if len(result) > 3800:
            assert "..." in result or "more" in result.lower()

    def test_timeline_with_drift_events(self):
        """Test formatting timeline with associated drift events."""
        records = [
            {
                "sync_record_id": 1,
                "planned_item_key": "event:Event 1",
                "status": "drift_detected",
                "external_object_id": "evt_001",
                "created_at": datetime(2024, 1, 15, 1, 0, 0),
                "last_error_summary": None,
                "drift_event": {
                    "event_id": 1,
                    "summary": "Rescheduled",
                    "details": {"field_diffs": {"start": {"before": "10:00", "after": "11:00"}}},
                    "created_at": datetime(2024, 1, 15, 1, 0, 0),
                },
            }
        ]
        result = format_sync_timeline(records)
        assert "Event 1" in result
        assert "start" in result
        assert "10:00" in result
        assert "11:00" in result

    def test_timeline_with_malformed_drift_event(self):
        """Test that malformed drift events don't crash the timeline formatter."""
        records = [
            {
                "sync_record_id": 1,
                "planned_item_key": "event:Event with bad drift",
                "status": "drift_detected",
                "external_object_id": "evt_bad",
                "created_at": datetime(2024, 1, 15, 1, 0, 0),
                "last_error_summary": None,
                "drift_event": {
                    "event_id": 1,
                    "summary": "Rescheduled",
                    "details": {"field_diffs": "malformed"},  # Not a dict
                    "created_at": datetime(2024, 1, 15, 1, 0, 0),
                },
            }
        ]
        result = format_sync_timeline(records)
        # Should not crash and should still show record line
        assert "Event with bad drift" in result

    def test_empty_records_with_max_events(self):
        """Test empty records with max_events parameter."""
        result = format_sync_timeline([], max_events=10)
        assert result == ""

    def test_status_symbols_in_timeline(self):
        """Test that all status symbols appear correctly in timeline."""
        records = [
            {
                "sync_record_id": 1,
                "planned_item_key": "task:Succeeded",
                "status": "succeeded",
                "external_object_id": "tsk_001",
                "created_at": datetime(2024, 1, 15, 1, 0, 0),
                "last_error_summary": None,
                "drift_event": None,
            },
            {
                "sync_record_id": 2,
                "planned_item_key": "task:Drifted",
                "status": "drift_detected",
                "external_object_id": "tsk_002",
                "created_at": datetime(2024, 1, 15, 2, 0, 0),
                "last_error_summary": None,
                "drift_event": None,
            },
            {
                "sync_record_id": 3,
                "planned_item_key": "task:Failed",
                "status": "failed",
                "external_object_id": "tsk_003",
                "created_at": datetime(2024, 1, 15, 3, 0, 0),
                "last_error_summary": None,
                "drift_event": None,
            },
        ]
        result = format_sync_timeline(records)
        assert "✓" in result
        assert "⚠" in result
        assert "✗" in result
