from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from helm_orchestration.schemas import ApprovalAction, ApprovalDecision, TaskSemantics


class PastEventError(ValueError):
    """Raised when a scheduled datetime is in the past."""


class ApprovalPolicy(Protocol):
    def evaluate(self, semantics: TaskSemantics) -> ApprovalDecision: ...


class ConditionalApprovalPolicy:
    """Auto-approve high-confidence short tasks, request revision otherwise.

    Tasks meeting both the confidence threshold and the sizing limit are
    approved automatically.  All others are returned for human review.
    """

    CONFIDENCE_THRESHOLD: float = 0.8
    MAX_AUTO_APPROVE_MINUTES: int = 120

    def evaluate(self, semantics: TaskSemantics) -> ApprovalDecision:
        if (
            semantics.confidence >= self.CONFIDENCE_THRESHOLD
            and semantics.sizing_minutes <= self.MAX_AUTO_APPROVE_MINUTES
        ):
            return ApprovalDecision(
                action=ApprovalAction.APPROVE,
                actor="system:conditional_policy",
                target_artifact_id=0,
            )
        return ApprovalDecision(
            action=ApprovalAction.REQUEST_REVISION,
            actor="system:conditional_policy",
            target_artifact_id=0,
            revision_feedback="Confidence or sizing outside auto-approve thresholds",
        )


# ---------------------------------------------------------------------------
# Timezone-aware scheduling primitives
# ---------------------------------------------------------------------------

_DAY_OFFSETS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_TIME_PATTERN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE
)

_RANGE_PATTERN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*[-\u2013]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
    re.IGNORECASE,
)


def compute_reference_week(tz: ZoneInfo) -> datetime:
    """Return the Monday of the current week at midnight in the given timezone.

    'Current week' means the ISO week containing today in the given timezone.
    If today is Sunday, returns the Monday 6 days ago (ISO week convention —
    week starts on Monday). The returned datetime is timezone-aware (tzinfo=tz).
    """
    now = datetime.now(tz)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def parse_local_slot(title: str, week_start: datetime, tz: ZoneInfo) -> datetime | None:
    """Extract day + start time from a task title like 'Monday deep work 10am-12pm'.

    Returns a timezone-aware datetime in `tz` for the named day at the named time,
    relative to the Monday of `week_start`'s week. Returns None if no day or time
    can be parsed.

    Behavior:
    - Searches title for day name (monday, tuesday, ..., sunday)
    - Searches for a time range (e.g. '10am-12pm') first, then a single time (e.g. '10am')
    - If day found but no time, defaults to 9am local
    - If no day found, returns None
    - Returned datetime is always timezone-aware (tzinfo=tz), NOT UTC
    """
    lowered = title.lower()

    # Find day offset
    day_offset: int | None = None
    for day, offset in _DAY_OFFSETS.items():
        if day in lowered:
            day_offset = offset
            break
    if day_offset is None:
        return None

    # Monday of reference week
    week_monday = week_start - timedelta(days=week_start.weekday())
    base_day = (week_monday + timedelta(days=day_offset)).replace(tzinfo=tz)

    # Find start time — prefer a range match (e.g. "10am-12pm"), fall back to first time
    range_match = _RANGE_PATTERN.search(title)
    if range_match:
        hour = int(range_match.group(1))
        minute = int(range_match.group(2) or 0)
        start_ampm = range_match.group(3) or range_match.group(6)
        if start_ampm and start_ampm.lower() == "pm" and hour != 12:
            hour += 12
        elif start_ampm and start_ampm.lower() == "am" and hour == 12:
            hour = 0
        return base_day.replace(hour=hour, minute=minute, second=0, microsecond=0)

    time_match = _TIME_PATTERN.search(title)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        ampm = time_match.group(3).lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        return base_day.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Day found but no time — use 9am default
    return base_day.replace(hour=9, minute=0, second=0, microsecond=0)


def to_utc(local_dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert a local datetime to UTC.

    If `local_dt` is already timezone-aware, returns it converted to UTC.
    If `local_dt` is naive, treats it as being in `tz`, then converts to UTC.
    """
    if local_dt.tzinfo is not None:
        return local_dt.astimezone(UTC)
    return local_dt.replace(tzinfo=tz).astimezone(UTC)


def past_event_guard(dt: datetime, tz: ZoneInfo) -> None:
    """Raise PastEventError if dt is in the past relative to now in tz.

    Compares `dt` (converted to UTC) against `datetime.now(UTC)`.
    Raises PastEventError with a descriptive message if the datetime is in the past.
    """
    utc_dt = to_utc(dt, tz)
    if utc_dt < datetime.now(UTC):
        raise PastEventError(
            f"Scheduled datetime {utc_dt.isoformat()} is in the past"
        )
