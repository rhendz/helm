from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime
from email_agent.send import send_approved_draft

MAX_AUTOMATIC_SEND_ATTEMPTS = 3
RETRYABLE_FAILURE_CLASSES = {
    "timeout",
    "connection_error",
    "rate_limited",
    "provider_5xx",
}


@dataclass(slots=True, frozen=True)
class SendRetryResult:
    draft_id: int
    action: str
    reason: str | None = None
    attempt_id: int | None = None
    sent: bool = False


def run_pending_send_retries(
    *,
    runtime: EmailAgentRuntime,
    limit: int = 20,
) -> list[SendRetryResult]:
    try:
        drafts = runtime.list_email_drafts(
            status="send_failed",
            approval_status="approved",
            limit=limit,
        )
    except SQLAlchemyError:
        return []

    results: list[SendRetryResult] = []
    for draft in drafts:
        draft_id = int(draft["id"])
        if runtime.has_successful_send_for_draft(draft_id=draft_id):
            results.append(
                SendRetryResult(
                    draft_id=draft_id,
                    action="skipped",
                    reason="already_succeeded",
                )
            )
            continue

        detail = runtime.get_email_draft_by_id(draft_id)
        if detail is None:
            results.append(
                SendRetryResult(
                    draft_id=draft_id,
                    action="skipped",
                    reason="draft_not_found",
                )
            )
            continue
        if detail.get("final_sent_message_id") is not None:
            results.append(
                SendRetryResult(
                    draft_id=draft_id,
                    action="skipped",
                    reason="already_sent",
                )
            )
            continue

        attempts = runtime.list_send_attempts_for_draft(draft_id=draft_id)
        if not attempts:
            results.append(
                SendRetryResult(
                    draft_id=draft_id,
                    action="skipped",
                    reason="no_prior_attempt",
                )
            )
            continue

        latest_attempt = attempts[0]
        if latest_attempt["status"] != "failed":
            results.append(
                SendRetryResult(
                    draft_id=draft_id,
                    action="skipped",
                    reason="latest_attempt_not_failed",
                )
            )
            continue

        failure_class = str(latest_attempt.get("failure_class") or "")
        if failure_class not in RETRYABLE_FAILURE_CLASSES:
            results.append(
                SendRetryResult(
                    draft_id=draft_id,
                    action="skipped",
                    reason="non_retryable_failure",
                )
            )
            continue

        if len(attempts) >= MAX_AUTOMATIC_SEND_ATTEMPTS:
            results.append(
                SendRetryResult(
                    draft_id=draft_id,
                    action="skipped",
                    reason="automatic_attempts_exhausted",
                )
            )
            continue

        send_result = send_approved_draft(draft_id=draft_id, runtime=runtime)
        results.append(
            SendRetryResult(
                draft_id=draft_id,
                action="retried",
                reason=send_result.reason,
                attempt_id=send_result.attempt_id,
                sent=send_result.sent,
            )
        )

    return results
