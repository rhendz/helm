from email_agent.runtime import ThreadRecord
from email_agent.thread_state import (
    transition_for_human_override,
    transition_for_inbound,
    transition_for_needs_review,
    transition_for_resolve,
    transition_for_scheduled_task,
)


def _thread(**overrides) -> ThreadRecord:
    payload = {
        "id": 7,
        "business_state": "waiting_on_other_party",
        "visible_labels": "Urgent",
        "current_summary": "Waiting for reply",
        "latest_confidence_band": "High",
        "resurfacing_source": None,
        "action_reason": None,
        "last_message_id": 11,
        "last_inbound_message_id": 11,
        "last_outbound_message_id": 12,
    }
    payload.update(overrides)
    return ThreadRecord(**payload)


def test_inbound_transition_sets_waiting_on_user_for_actionable_thread() -> None:
    update = transition_for_inbound(
        classification="urgent",
        priority_score=1,
        thread_summary="Need response",
        action_item_required=True,
        draft_reply_required=True,
        email_message_id=22,
        previous_thread=_thread(),
    )

    assert update.business_state == "waiting_on_user"
    assert update.visible_labels == ("Action", "Urgent")
    assert update.resurfacing_source == "new_message"
    assert update.action_reason == "reply_needed"
    assert update.last_outbound_message_id == 12


def test_scheduled_followup_preserves_waiting_on_other_party_state() -> None:
    update = transition_for_scheduled_task(_thread(), task_type="followup")

    assert update.business_state == "waiting_on_other_party"
    assert update.visible_labels == ("Action", "Urgent")
    assert update.resurfacing_source == "stale_followup"
    assert update.action_reason == "followup_due"


def test_scheduled_reminder_resurfaces_without_business_state_change() -> None:
    update = transition_for_scheduled_task(
        _thread(business_state="waiting_on_user", visible_labels="Action"),
        task_type="reminder",
    )

    assert update.business_state == "waiting_on_user"
    assert update.visible_labels == ("Action",)
    assert update.resurfacing_source == "reminder_due"
    assert update.action_reason == "reminder_due"


def test_human_override_uses_override_as_source_of_truth() -> None:
    update = transition_for_human_override(
        _thread(),
        business_state="resolved",
        visible_labels=("NeedsReview", "NeedsReview"),
        current_summary="Closed manually",
        latest_confidence_band="Low",
        action_reason="user_marked_done",
    )

    assert update.business_state == "resolved"
    assert update.visible_labels == ("NeedsReview",)
    assert update.resurfacing_source == "user_override"
    assert update.current_summary == "Closed manually"


def test_human_override_rejects_unknown_state() -> None:
    try:
        transition_for_human_override(
            _thread(),
            business_state="not_real",
            visible_labels=(),
            current_summary=None,
            latest_confidence_band=None,
            action_reason=None,
        )
    except ValueError as exc:
        assert "Unknown business state" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_resolve_transition_clears_labels_and_marks_override() -> None:
    update = transition_for_resolve(_thread())

    assert update.business_state == "resolved"
    assert update.visible_labels == ()
    assert update.resurfacing_source == "user_override"
    assert update.action_reason == "user_marked_done"


def test_needs_review_transition_adds_label() -> None:
    update = transition_for_needs_review(_thread(visible_labels="Action"))

    assert update.business_state == "needs_review"
    assert update.visible_labels == ("Action", "NeedsReview")
    assert update.resurfacing_source == "user_override"
    assert update.action_reason == "user_requested_review"
