"""Unit tests for scheduling primitives in helm_orchestration.scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from helm_orchestration.scheduling import (
    PastEventError,
    compute_reference_week,
    parse_local_slot,
    past_event_guard,
    to_utc,
)

TZ = ZoneInfo("America/Los_Angeles")

# ---------------------------------------------------------------------------
# compute_reference_week
# ---------------------------------------------------------------------------


def test_compute_reference_week_returns_monday():
    result = compute_reference_week(TZ)
    assert result.weekday() == 0, f"Expected Monday (0), got {result.weekday()}"


def test_compute_reference_week_is_tz_aware():
    result = compute_reference_week(TZ)
    assert result.tzinfo is not None


def test_compute_reference_week_midnight():
    result = compute_reference_week(TZ)
    assert result.hour == 0
    assert result.minute == 0
    assert result.second == 0
    assert result.microsecond == 0


# ---------------------------------------------------------------------------
# parse_local_slot
# ---------------------------------------------------------------------------

# Use a Monday in summer (PDT = UTC-7) as week_start reference
_WEEK_START = datetime(2026, 6, 15, 0, 0, tzinfo=TZ)  # June 15 2026 is a Monday


def test_parse_local_slot_day_and_time():
    result = parse_local_slot("Monday deep work 10am", _WEEK_START, TZ)
    assert result is not None
    assert result.hour == 10
    assert result.tzinfo is not None


def test_parse_local_slot_range():
    result = parse_local_slot("Tuesday 10am-12pm", _WEEK_START, TZ)
    assert result is not None
    assert result.hour == 10
    assert result.weekday() == 1  # Tuesday


def test_parse_local_slot_no_day_returns_none():
    result = parse_local_slot("deep work 10am", _WEEK_START, TZ)
    assert result is None


def test_parse_local_slot_day_no_time_defaults_9am():
    result = parse_local_slot("Wednesday deep work", _WEEK_START, TZ)
    assert result is not None
    assert result.hour == 9
    assert result.weekday() == 2  # Wednesday


def test_parse_local_slot_returns_local_tz_not_utc():
    """Returned datetime must be in the given tz, not UTC."""
    result = parse_local_slot("Friday focus 3pm", _WEEK_START, TZ)
    assert result is not None
    assert result.tzinfo is not None
    # Should be in LA tz, not UTC
    assert result.tzinfo == TZ


def test_parse_local_slot_pm_time():
    result = parse_local_slot("Thursday standup 2pm", _WEEK_START, TZ)
    assert result is not None
    assert result.hour == 14


def test_parse_local_slot_midnight_hour():
    """12am should resolve to hour=0."""
    result = parse_local_slot("Monday late 12am", _WEEK_START, TZ)
    assert result is not None
    assert result.hour == 0


def test_parse_local_slot_noon():
    """12pm should resolve to hour=12."""
    result = parse_local_slot("Monday lunch 12pm", _WEEK_START, TZ)
    assert result is not None
    assert result.hour == 12


# ---------------------------------------------------------------------------
# to_utc
# ---------------------------------------------------------------------------


def test_to_utc_naive_input():
    """Naive datetime in PDT (UTC-7) should convert to hour+7 in UTC."""
    # June 15 2026 10:00 PDT = June 15 2026 17:00 UTC
    naive = datetime(2026, 6, 15, 10, 0)
    result = to_utc(naive, TZ)
    assert result.tzinfo == UTC or result.utcoffset().total_seconds() == 0
    assert result.hour == 17
    assert result.year == 2026
    assert result.month == 6
    assert result.day == 15


def test_to_utc_aware_input():
    """Already-aware datetime should convert to UTC correctly."""
    aware = datetime(2026, 6, 15, 10, 0, tzinfo=TZ)
    result = to_utc(aware, TZ)
    assert result.utcoffset().total_seconds() == 0
    assert result.hour == 17


def test_to_utc_utc_input_unchanged():
    """UTC datetime stays UTC."""
    utc_dt = datetime(2026, 6, 15, 17, 0, tzinfo=UTC)
    result = to_utc(utc_dt, TZ)
    assert result.hour == 17
    assert result.utcoffset().total_seconds() == 0


# ---------------------------------------------------------------------------
# past_event_guard
# ---------------------------------------------------------------------------


def test_past_event_guard_future_does_not_raise():
    far_future = datetime(2099, 1, 1, 12, 0, tzinfo=UTC)
    # Should not raise
    past_event_guard(far_future, TZ)


def test_past_event_guard_past_raises():
    past_dt = datetime(2020, 1, 1, 12, 0, tzinfo=UTC)
    with pytest.raises(PastEventError):
        past_event_guard(past_dt, TZ)


def test_past_event_guard_past_raises_type():
    past_dt = datetime(2020, 6, 1, 9, 0, tzinfo=UTC)
    with pytest.raises(PastEventError) as exc_info:
        past_event_guard(past_dt, TZ)
    assert isinstance(exc_info.value, ValueError)


def test_past_event_guard_error_message_contains_iso():
    past_dt = datetime(2020, 3, 15, 8, 0, tzinfo=UTC)
    with pytest.raises(PastEventError, match="2020-03-15"):
        past_event_guard(past_dt, TZ)
