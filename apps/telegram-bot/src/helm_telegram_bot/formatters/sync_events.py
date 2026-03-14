"""Formatters for workflow sync events and drift detection.

This module transforms sync records and drift events from the database into human-readable
Telegram messages that operators can understand at a glance.

Contracts:
- All formatters handle missing/malformed fields defensively using .get() with defaults.
- Status symbols: "✓" for SUCCEEDED, "⚠" for DRIFT_DETECTED, "✗" for FAILED, "⏳" for others.
- Long titles are truncated to 40 chars to keep messages compact.
- Telegram has a 4096-character message limit; timelines are truncated gracefully with
  indication of remaining events if the limit is approached.

Edge cases:
- Missing planned_item_key: Falls back to external_object_id or "(unknown item)".
- Missing title: Uses planned_item_key or external_object_id as context.
- Empty field_diffs: Renders as "(no changes recorded)".
- Malformed drift event details: Logged but does not crash; fallback message used.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Telegram message size limit with safety margin
TELEGRAM_MESSAGE_LIMIT = 3800


def format_sync_record(record: dict[str, Any]) -> str:
    """Format a single sync record as a concise one-line summary.

    Args:
        record: Dict with keys sync_record_id, planned_item_key, status, external_object_id,
                created_at, last_error_summary, drift_event (optional).

    Returns:
        Single-line formatted string with status symbol, item context, and timestamp.
        Example: "✓ Task: Weekly meeting (evt_123abc) synced at 02:35:10"
    """
    status = record.get("status", "unknown")
    planned_item_key = record.get("planned_item_key", "")
    external_object_id = record.get("external_object_id", "")
    created_at = record.get("created_at")

    # Determine status symbol
    if status == "succeeded":
        symbol = "✓"
    elif status == "drift_detected":
        symbol = "⚠"
    elif status == "failed":
        symbol = "✗"
    else:
        symbol = "⏳"

    # Extract item type and title from planned_item_key
    # Format is typically "type:id" or "type:title"
    item_type = "Item"
    item_context = ""
    if planned_item_key:
        parts = planned_item_key.split(":", 1)
        if len(parts) == 2:
            item_type = parts[0].title()  # e.g., "Task" from "task"
            item_context = parts[1]
    else:
        item_context = external_object_id or "(unknown item)"

    # Truncate long titles to keep message compact
    if len(item_context) > 40:
        item_context = item_context[:37] + "..."

    # Format timestamp (HH:MM:SS if datetime object present)
    timestamp_str = "n/a"
    if created_at:
        try:
            # Handle both datetime objects and string timestamps
            if hasattr(created_at, "strftime"):
                timestamp_str = created_at.strftime("%H:%M:%S")
            else:
                timestamp_str = str(created_at)[-8:] if len(str(created_at)) >= 8 else str(created_at)
        except Exception:
            timestamp_str = "n/a"

    return f"{symbol} {item_type}: {item_context} ({external_object_id or 'unknown'}) synced at {timestamp_str}"


def format_drift_event(event: dict[str, Any], sync_record: dict[str, Any]) -> str:
    """Format a drift event with field-level changes.

    Args:
        event: Dict with keys event_id, summary, details (dict with field_diffs), created_at.
        sync_record: Associated sync record for context (planned_item_key, etc.).

    Returns:
        Multi-line formatted string describing what changed.
        Example:
            Event Y rescheduled:
              start changed from 10:00 to 14:00
              location changed from "Office" to "Remote"
    """
    details = event.get("details", {})
    planned_item_key = sync_record.get("planned_item_key", "Unknown")

    # Extract field_diffs from details (format: {"field_name": {"before": value, "after": value}})
    field_diffs = {}
    if isinstance(details, dict):
        field_diffs = details.get("field_diffs", {})

    if not isinstance(field_diffs, dict):
        logger.debug("malformed_field_diffs", extra={"event_id": event.get("event_id"), "details": details})
        return f"Event {planned_item_key} drifted; see logs for details"

    if not field_diffs:
        return f"Event {planned_item_key} drifted: (no changes recorded)"

    # Build diff lines
    diff_lines = [f"Event {planned_item_key} drifted:"]
    for field_name, changes in field_diffs.items():
        if not isinstance(changes, dict):
            continue
        before = changes.get("before")
        after = changes.get("after")
        diff_lines.append(f"  {field_name} changed from {before!r} to {after!r}")

    return "\n".join(diff_lines)


def format_sync_timeline(
    sync_records: list[dict[str, Any]],
    drift_events: dict[int, dict[str, Any]] | None = None,
    max_events: int = 8,
) -> str:
    """Format a timeline of recent sync events with truncation for Telegram message limits.

    Args:
        sync_records: List of sync event dicts (from list_sync_events()).
        drift_events: Optional dict mapping sync_record_id to drift event dicts.
        max_events: Maximum number of sync events to display (default 8).

    Returns:
        Multi-line formatted timeline string, or empty string if no records.
        If timeline exceeds TELEGRAM_MESSAGE_LIMIT or there are more records than max_events,
        truncates and appends "... and N more events".
        Logs truncation_applied flag for observability.
    """
    if not sync_records:
        return ""

    if drift_events is None:
        drift_events = {}

    # Build timeline lines
    timeline_lines = []
    records_to_show = sync_records[:max_events]

    for record in records_to_show:
        # Format the sync record
        record_line = format_sync_record(record)
        timeline_lines.append(record_line)

        # Append drift event if present
        drift_event = record.get("drift_event")
        if drift_event and isinstance(drift_event, dict):
            try:
                drift_line = format_drift_event(drift_event, record)
                timeline_lines.append(drift_line)
            except Exception:  # noqa: F841
                logger.exception("drift_format_error", extra={"record_id": record.get("sync_record_id")})
                timeline_lines.append("  (drift details unavailable; see logs)")

    # Join and check size
    timeline_str = "\n".join(timeline_lines)

    truncation_applied = False
    remaining = len(sync_records) - len(records_to_show)

    # Truncate if message size exceeds limit
    if len(timeline_str) > TELEGRAM_MESSAGE_LIMIT:
        truncation_applied = True
        timeline_str = timeline_str[:TELEGRAM_MESSAGE_LIMIT]
        timeline_str += f"\n... and {remaining + len(records_to_show)} events total (showing {len(records_to_show)})"
    # Or if there are more records than max_events
    elif remaining > 0:
        truncation_applied = True
        timeline_str += f"\n... and {remaining} more events"

    logger.debug(
        "sync_timeline_formatted",
        extra={
            "record_count": len(records_to_show),
            "truncation_applied": truncation_applied,
            "message_length": len(timeline_str),
        },
    )

    return timeline_str
