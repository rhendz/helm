from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from helm_connectors.gmail import GmailSendError, send_reply
from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime


@dataclass(frozen=True, slots=True)
class SendDraftResult:
    status: str
    draft_id: int
    attempt_id: int | None
    sent: bool
    reason: str | None = None
    warning: str | None = None
    final_sent_message_id: int | None = None


def send_approved_draft(
    *,
    draft_id: int,
    runtime: EmailAgentRuntime,
) -> SendDraftResult:
    try:
        draft = runtime.get_email_draft_by_id(draft_id)
        if draft is None:
            return SendDraftResult(
                status="not_found",
                draft_id=draft_id,
                attempt_id=None,
                sent=False,
                reason="draft_not_found",
            )
        if draft["approval_status"] != "approved":
            return SendDraftResult(
                status="rejected",
                draft_id=draft_id,
                attempt_id=None,
                sent=False,
                reason="approval_required",
            )

        attempt = runtime.create_send_attempt(
            draft_id=draft_id,
            email_thread_id=draft["email_thread_id"],
            attempt_number=runtime.get_send_attempt_count_for_draft(draft_id=draft_id) + 1,
            started_at=datetime.now(tz=UTC),
        )

        if runtime.has_successful_send_for_draft(draft_id=draft_id):
            runtime.complete_send_attempt(
                attempt_id=attempt.id,
                status="failed",
                completed_at=datetime.now(tz=UTC),
                failure_class="duplicate_send",
                failure_message="Local duplicate-send protection blocked another successful send.",
            )
            return SendDraftResult(
                status="rejected",
                draft_id=draft_id,
                attempt_id=attempt.id,
                sent=False,
                reason="duplicate_send",
                warning="This draft already has a confirmed successful send.",
            )

        latest_inbound = runtime.get_latest_inbound_email_message(
            thread_id=draft["email_thread_id"]
        )
        if latest_inbound is None or not str(latest_inbound.get("from_address") or "").strip():
            runtime.complete_send_attempt(
                attempt_id=attempt.id,
                status="failed",
                completed_at=datetime.now(tz=UTC),
                failure_class="invalid_recipient",
                failure_message="No reply recipient could be derived from the thread.",
            )
            runtime.set_email_draft_status(draft_id, status="send_failed")
            return SendDraftResult(
                status="failed",
                draft_id=draft_id,
                attempt_id=attempt.id,
                sent=False,
                reason="invalid_recipient",
            )

        thread = runtime.get_thread_by_id(draft["email_thread_id"])
        if thread is None:
            runtime.complete_send_attempt(
                attempt_id=attempt.id,
                status="failed",
                completed_at=datetime.now(tz=UTC),
                failure_class="invalid_payload",
                failure_message="Draft thread no longer exists.",
            )
            runtime.set_email_draft_status(draft_id, status="send_failed")
            return SendDraftResult(
                status="failed",
                draft_id=draft_id,
                attempt_id=attempt.id,
                sent=False,
                reason="thread_not_found",
            )

        try:
            send_result = send_reply(
                provider_thread_id=str(latest_inbound["provider_thread_id"]),
                to_address=str(latest_inbound["from_address"]),
                subject=str(draft.get("draft_subject") or latest_inbound.get("subject") or ""),
                body_text=str(draft["draft_body"]),
            )
        except GmailSendError as exc:
            runtime.complete_send_attempt(
                attempt_id=attempt.id,
                status="failed",
                completed_at=datetime.now(tz=UTC),
                failure_class=exc.failure_class,
                failure_message=str(exc),
                provider_error_code=exc.provider_error_code,
            )
            runtime.set_email_draft_status(draft_id, status="send_failed")
            warning = (
                "Delivery state is unknown. Manual retry may duplicate-send."
                if exc.failure_class == "unknown_delivery_state"
                else None
            )
            return SendDraftResult(
                status="failed",
                draft_id=draft_id,
                attempt_id=attempt.id,
                sent=False,
                reason=exc.failure_class,
                warning=warning,
            )

        outbound_message = runtime.create_outbound_email_message(
            provider_message_id=send_result.provider_message_id,
            provider_thread_id=send_result.provider_thread_id,
            email_thread_id=draft["email_thread_id"],
            source_draft_id=draft_id,
            from_address=send_result.from_address,
            to_addresses=(send_result.to_address,),
            subject=send_result.subject,
            body_text=send_result.body_text,
            received_at=send_result.sent_at,
            normalized_at=send_result.sent_at,
            source=send_result.source,
        )
        runtime.complete_send_attempt(
            attempt_id=attempt.id,
            status="succeeded",
            completed_at=send_result.sent_at,
            provider_message_id=send_result.provider_message_id,
        )
        runtime.set_email_draft_status(draft_id, status="generated")
        runtime.set_email_draft_final_sent_message(draft_id, message_id=outbound_message.id)
        runtime.update_thread_state(
            draft["email_thread_id"],
            business_state=thread.business_state,
            visible_labels=tuple(_split_labels(thread.visible_labels)),
            latest_confidence_band=thread.latest_confidence_band,
            resurfacing_source=thread.resurfacing_source,
            action_reason=thread.action_reason,
            current_summary=thread.current_summary,
            last_message_id=outbound_message.id,
            last_inbound_message_id=thread.last_inbound_message_id,
            last_outbound_message_id=outbound_message.id,
        )
    except SQLAlchemyError:
        return SendDraftResult(
            status="unavailable",
            draft_id=draft_id,
            attempt_id=None,
            sent=False,
            reason="storage_unavailable",
        )

    return SendDraftResult(
        status="accepted",
        draft_id=draft_id,
        attempt_id=attempt.id,
        sent=True,
        final_sent_message_id=outbound_message.id,
    )


def _split_labels(value: str) -> list[str]:
    if not value:
        return []
    return [label for label in value.split(",") if label]
