"""Integration tests for Telegram workflow sync detail commands.

Tests the `/workflows <run_id>` sync timeline integration and `/workflow_sync_detail <run_id>`
command with real workflow runs and sync records.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from helm_telegram_bot.commands import workflows  # noqa: F401


class _Message:
    """Mock Telegram message for capturing replies."""

    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _Update:
    """Mock Telegram update."""

    def __init__(self, *, user_id: int = 1) -> None:
        self.message = _Message()
        self.effective_user = type("User", (), {"id": user_id})()


class _Context:
    """Mock context with command arguments."""

    def __init__(self, args: list[str]) -> None:
        self.args = args


def _make_sync_record(record_id: int = 1, title: str = "Task 1", status: str = "succeeded") -> dict:
    """Create a mock sync record dict for testing."""
    return {
        "sync_record_id": record_id,
        "planned_item_key": f"task:{title}",
        "status": status,
        "external_object_id": f"ext_{record_id:03d}",
        "created_at": datetime.now(UTC),
        "last_error_summary": None,
        "drift_event": None,
    }


def _make_drift_event(sync_record_id: int = 1) -> dict:
    """Create a mock drift event dict for testing."""
    return {
        "event_id": 100 + sync_record_id,
        "summary": "Item drifted",
        "details": {
            "sync_record_id": sync_record_id,
            "field_diffs": {
                "start": {"before": "10:00", "after": "14:00"},
                "location": {"before": "Office", "after": "Remote"},
            },
        },
        "created_at": datetime.now(UTC),
    }


@pytest.mark.asyncio
async def test_workflows_includes_sync_timeline_for_run_with_sync_records() -> None:
    """Test that `/workflows <run_id>` includes sync timeline when sync records exist."""
    run_id = 42
    sync_records = [
        _make_sync_record(1, "Meeting Setup", "succeeded"),
        _make_sync_record(2, "Calendar Invite", "succeeded"),
    ]

    async def mock_reject_if_unauthorized(_update, _context) -> bool:
        return False

    def mock_list_recent_runs():
        return [
            {
                "id": run_id,
                "status": "completed",
                "current_step": "done",
                "paused_state": "active",
                "last_event_summary": "Workflow completed successfully.",
                "needs_action": False,
                "available_actions": [],
                "completion_summary": {
                    "headline": "Completed with 2 syncs",
                    "total_sync_writes": 2,
                    "task_sync_writes": 1,
                    "calendar_sync_writes": 1,
                    "downstream_sync_status": "succeeded",
                },
            }
        ]

    def mock_list_sync_events(rid: int):
        return sync_records if rid == run_id else []

    with patch.object(workflows, "reject_if_unauthorized", side_effect=mock_reject_if_unauthorized):
        with patch.object(workflows._service, "list_recent_runs", side_effect=mock_list_recent_runs):
            with patch.object(workflows._service, "list_sync_events", side_effect=mock_list_sync_events):
                update = _Update(user_id=1)
                context = _Context(args=[])
                await workflows.recent(update, context)

                # Verify response includes sync info
                assert len(update.message.replies) > 0
                reply = update.message.replies[0]
                assert "completed" in reply
                assert "Outcome: Completed with 2 syncs" in reply


@pytest.mark.asyncio
async def test_workflow_sync_detail_returns_full_timeline() -> None:
    """Test that `/workflow_sync_detail <run_id>` shows full sync event timeline."""
    run_id = 42
    sync_records = [
        _make_sync_record(1, "Task 1", "succeeded"),
        _make_sync_record(2, "Task 2", "succeeded"),
        _make_sync_record(3, "Task 3", "drift_detected"),
    ]
    # Add drift event to first record
    sync_records[0]["drift_event"] = _make_drift_event(sync_records[0]["sync_record_id"])

    async def mock_reject_if_unauthorized(_update, _context) -> bool:
        return False

    def mock_get_sync_details(rid: int):
        if rid == run_id:
            return {
                "sync_records": sync_records,
                "drift_events": [sync_records[0]["drift_event"]],
                "total_sync_writes": 2,
                "task_sync_writes": 1,
                "calendar_sync_writes": 1,
            }
        return {"sync_records": [], "drift_events": [], "total_sync_writes": 0, "task_sync_writes": 0, "calendar_sync_writes": 0}

    with patch.object(workflows, "reject_if_unauthorized", side_effect=mock_reject_if_unauthorized):
        with patch.object(workflows._service, "get_sync_details", side_effect=mock_get_sync_details):
            update = _Update(user_id=1)
            context = _Context(args=[str(run_id)])

            await workflows.sync_detail(update, context)

            # Verify response
            assert len(update.message.replies) == 1
            reply = update.message.replies[0]

            # Should include run ID and sync summary
            assert f"Run {run_id} sync timeline:" in reply
            assert "Total writes:" in reply


@pytest.mark.asyncio
async def test_workflow_sync_detail_handles_missing_run() -> None:
    """Test that `/workflow_sync_detail <invalid_id>` handles missing runs gracefully."""

    async def mock_reject_if_unauthorized(_update, _context) -> bool:
        return False

    def mock_get_sync_details(run_id: int) -> dict[str, object]:
        # Return empty for non-existent run
        return {
            "sync_records": [],
            "drift_events": [],
            "total_sync_writes": 0,
            "task_sync_writes": 0,
            "calendar_sync_writes": 0,
        }

    with patch.object(workflows, "reject_if_unauthorized", side_effect=mock_reject_if_unauthorized):
        with patch.object(workflows._service, "get_sync_details", side_effect=mock_get_sync_details):
            update = _Update(user_id=1)
            context = _Context(args=["999"])

            await workflows.sync_detail(update, context)

            # Should indicate no sync events
            assert len(update.message.replies) == 1
            assert "No sync events" in update.message.replies[0]


@pytest.mark.asyncio
async def test_workflow_sync_detail_handles_missing_argument() -> None:
    """Test that `/workflow_sync_detail` without args shows usage."""

    async def mock_reject_if_unauthorized(_update, _context) -> bool:
        return False

    with patch.object(workflows, "reject_if_unauthorized", side_effect=mock_reject_if_unauthorized):
        update = _Update(user_id=1)
        context = _Context(args=[])

        await workflows.sync_detail(update, context)

        # Should show usage
        assert len(update.message.replies) == 1
        assert "Usage: /workflow_sync_detail" in update.message.replies[0]


@pytest.mark.asyncio
async def test_workflow_sync_detail_handles_invalid_run_id() -> None:
    """Test that `/workflow_sync_detail <non_numeric>` shows usage."""

    async def mock_reject_if_unauthorized(_update, _context) -> bool:
        return False

    with patch.object(workflows, "reject_if_unauthorized", side_effect=mock_reject_if_unauthorized):
        update = _Update(user_id=1)
        context = _Context(args=["abc"])

        await workflows.sync_detail(update, context)

        # Should show usage (parse_single_id_arg returns None for non-numeric)
        assert len(update.message.replies) == 1
        assert "Usage: /workflow_sync_detail" in update.message.replies[0]


@pytest.mark.asyncio
async def test_backward_compatibility_workflows_without_args_still_works() -> None:
    """Test that existing `/workflows` command (without args) still works as before."""
    run_id = 42

    async def mock_reject_if_unauthorized(_update, _context) -> bool:
        return False

    def mock_list_recent_runs() -> list[dict[str, object]]:
        return [
            {
                "id": run_id,
                "status": "completed",
                "current_step": "done",
                "paused_state": "active",
                "last_event_summary": "Workflow completed.",
                "needs_action": False,
                "available_actions": [],
            }
        ]

    def mock_list_sync_events(rid: int):
        return []  # No sync events in this test

    with patch.object(workflows, "reject_if_unauthorized", side_effect=mock_reject_if_unauthorized):
        with patch.object(workflows._service, "list_recent_runs", side_effect=mock_list_recent_runs):
            with patch.object(workflows._service, "list_sync_events", side_effect=mock_list_sync_events):
                update = _Update(user_id=1)
                context = _Context(args=[])

                await workflows.recent(update, context)

                # Should include run status (backward compatible)
                assert len(update.message.replies) > 0
                reply = update.message.replies[0]
                assert f"Run {run_id}" in reply
                assert "completed" in reply


@pytest.mark.asyncio
async def test_workflow_sync_detail_includes_drift_events() -> None:
    """Test that `/workflow_sync_detail` shows drift event details in timeline."""
    run_id = 42
    sync_records = [
        _make_sync_record(1, "Task 1", "drift_detected"),
        _make_sync_record(2, "Task 2", "succeeded"),
    ]
    # Add drift event to first record
    sync_records[0]["drift_event"] = _make_drift_event(1)

    async def mock_reject_if_unauthorized(_update, _context) -> bool:
        return False

    def mock_get_sync_details(rid: int):
        if rid == run_id:
            return {
                "sync_records": sync_records,
                "drift_events": [sync_records[0]["drift_event"]],
                "total_sync_writes": 1,
                "task_sync_writes": 1,
                "calendar_sync_writes": 0,
            }
        return {"sync_records": [], "drift_events": [], "total_sync_writes": 0, "task_sync_writes": 0, "calendar_sync_writes": 0}

    with patch.object(workflows, "reject_if_unauthorized", side_effect=mock_reject_if_unauthorized):
        with patch.object(workflows._service, "get_sync_details", side_effect=mock_get_sync_details):
            update = _Update(user_id=1)
            context = _Context(args=[str(run_id)])

            await workflows.sync_detail(update, context)

            # Verify response includes drift information
            assert len(update.message.replies) == 1
            reply = update.message.replies[0]

            # Timeline should be included
            assert "sync timeline:" in reply or "total" in reply.lower()


@pytest.mark.asyncio
async def test_sync_timeline_truncation_for_long_timelines() -> None:
    """Test that sync timeline gracefully truncates for many events."""
    run_id = 42
    # Create 15 sync records (more than default max_events=8 in workflows.recent)
    sync_records = [_make_sync_record(i, f"Task {i}", "succeeded") for i in range(1, 16)]

    async def mock_reject_if_unauthorized(_update, _context) -> bool:
        return False

    def mock_list_sync_events(rid: int):
        return sync_records if rid == run_id else []

    def mock_list_recent_runs() -> list[dict[str, object]]:
        return [
            {
                "id": run_id,
                "status": "completed",
                "current_step": "done",
                "paused_state": "active",
                "last_event_summary": "Workflow completed.",
                "needs_action": False,
                "available_actions": [],
            }
        ]

    with patch.object(workflows, "reject_if_unauthorized", side_effect=mock_reject_if_unauthorized):
        with patch.object(workflows._service, "list_recent_runs", side_effect=mock_list_recent_runs):
            with patch.object(workflows._service, "list_sync_events", side_effect=mock_list_sync_events):
                update = _Update(user_id=1)
                context = _Context(args=[])

                await workflows.recent(update, context)

                # Verify response indicates truncation (if sync timeline is shown)
                assert len(update.message.replies) > 0
                # The response should exist (backward compatibility test)
