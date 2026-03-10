from __future__ import annotations

from dataclasses import dataclass

from email_agent.runtime import ThreadRecord

ALLOWED_BUSINESS_STATES = frozenset(
    {
        "uninitialized",
        "waiting_on_user",
        "waiting_on_other_party",
        "needs_review",
        "resolved",
    }
)


@dataclass(frozen=True, slots=True)
class ThreadStateUpdate:
    business_state: str
    visible_labels: tuple[str, ...]
    latest_confidence_band: str | None
    resurfacing_source: str | None
    action_reason: str | None
    current_summary: str | None
    last_message_id: int | None
    last_inbound_message_id: int | None
    last_outbound_message_id: int | None


def transition_for_inbound(
    *,
    classification: str,
    priority_score: int,
    thread_summary: str | None,
    action_item_required: bool,
    draft_reply_required: bool,
    email_message_id: int,
    previous_thread: ThreadRecord | None = None,
) -> ThreadStateUpdate:
    return ThreadStateUpdate(
        business_state="waiting_on_user" if action_item_required else "resolved",
        visible_labels=_derive_visible_labels(
            classification=classification,
            priority_score=priority_score,
            action_item_required=action_item_required,
        ),
        latest_confidence_band=_derive_confidence_band(
            classification=classification,
            priority_score=priority_score,
        ),
        resurfacing_source="new_message",
        action_reason=_derive_action_reason(
            action_item_required=action_item_required,
            draft_reply_required=draft_reply_required,
        ),
        current_summary=thread_summary,
        last_message_id=email_message_id,
        last_inbound_message_id=email_message_id,
        last_outbound_message_id=(
            previous_thread.last_outbound_message_id if previous_thread is not None else None
        ),
    )


def transition_for_scheduled_task(
    thread: ThreadRecord,
    *,
    task_type: str,
) -> ThreadStateUpdate:
    resurfacing_source, action_reason = _derive_task_metadata(task_type)
    return ThreadStateUpdate(
        business_state=thread.business_state,
        visible_labels=_merge_labels(thread.visible_labels, "Action"),
        latest_confidence_band=thread.latest_confidence_band,
        resurfacing_source=resurfacing_source,
        action_reason=action_reason,
        current_summary=thread.current_summary,
        last_message_id=thread.last_message_id,
        last_inbound_message_id=thread.last_inbound_message_id,
        last_outbound_message_id=thread.last_outbound_message_id,
    )


def transition_for_human_override(
    thread: ThreadRecord,
    *,
    business_state: str,
    visible_labels: tuple[str, ...],
    current_summary: str | None,
    latest_confidence_band: str | None,
    action_reason: str | None,
) -> ThreadStateUpdate:
    _require_known_state(business_state)
    return ThreadStateUpdate(
        business_state=business_state,
        visible_labels=tuple(sorted({label for label in visible_labels if label})),
        latest_confidence_band=latest_confidence_band,
        resurfacing_source="user_override",
        action_reason=action_reason,
        current_summary=current_summary,
        last_message_id=thread.last_message_id,
        last_inbound_message_id=thread.last_inbound_message_id,
        last_outbound_message_id=thread.last_outbound_message_id,
    )


def transition_for_resolve(thread: ThreadRecord) -> ThreadStateUpdate:
    return transition_for_human_override(
        thread,
        business_state="resolved",
        visible_labels=(),
        current_summary=thread.current_summary,
        latest_confidence_band=thread.latest_confidence_band,
        action_reason="user_marked_done",
    )


def transition_for_needs_review(thread: ThreadRecord) -> ThreadStateUpdate:
    return transition_for_human_override(
        thread,
        business_state="needs_review",
        visible_labels=_merge_labels(thread.visible_labels, "NeedsReview"),
        current_summary=thread.current_summary,
        latest_confidence_band=thread.latest_confidence_band,
        action_reason="user_requested_review",
    )


def _require_known_state(business_state: str) -> None:
    if business_state not in ALLOWED_BUSINESS_STATES:
        raise ValueError(f"Unknown business state: {business_state}")


def _merge_labels(
    serialized_or_labels: str | tuple[str, ...],
    *extra_labels: str,
) -> tuple[str, ...]:
    if isinstance(serialized_or_labels, str):
        labels = [label for label in serialized_or_labels.split(",") if label]
    else:
        labels = list(serialized_or_labels)
    labels.extend(extra_labels)
    return tuple(sorted(set(labels)))


def _derive_task_metadata(task_type: str) -> tuple[str, str]:
    if task_type == "followup":
        return "stale_followup", "followup_due"
    return "reminder_due", "reminder_due"


def _derive_action_reason(*, action_item_required: bool, draft_reply_required: bool) -> str | None:
    if draft_reply_required:
        return "reply_needed"
    if action_item_required:
        return "awareness_needed"
    return None


def _derive_visible_labels(
    *,
    classification: str,
    priority_score: int,
    action_item_required: bool,
) -> tuple[str, ...]:
    labels: list[str] = []
    if action_item_required:
        labels.append("Action")
    if classification == "urgent":
        labels.append("Urgent")
    if classification == "unclassified" and priority_score <= 2:
        labels.append("NeedsReview")
    return tuple(labels)


def _derive_confidence_band(*, classification: str, priority_score: int) -> str:
    if classification in {"opportunity", "urgent"} and priority_score <= 2:
        return "High"
    if classification == "unclassified":
        return "Medium"
    return "Low"
