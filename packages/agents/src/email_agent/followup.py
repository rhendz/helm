from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime


@dataclass(slots=True, frozen=True)
class FollowupScanResult:
    thread_id: int
    action: str
    reason: str
    task_id: int | None = None


def enqueue_stale_followups(
    *,
    runtime: EmailAgentRuntime,
    now: datetime | None = None,
    limit: int = 100,
) -> list[FollowupScanResult]:
    scan_time = _coerce_utc(now or datetime.now(tz=UTC))
    try:
        config = runtime.get_email_agent_config()
        threads = runtime.list_email_threads(
            business_state="waiting_on_other_party",
            limit=limit,
        )
    except SQLAlchemyError:
        return []

    results: list[FollowupScanResult] = []
    for thread in threads:
        thread_id = int(thread["id"])
        outbound = runtime.get_latest_outbound_email_message(thread_id=thread_id)
        if outbound is None:
            results.append(
                FollowupScanResult(
                    thread_id=thread_id,
                    action="skipped",
                    reason="no_outbound_message",
                )
            )
            continue

        latest_inbound = runtime.get_latest_inbound_email_message(thread_id=thread_id)
        outbound_received_at = _coerce_utc(outbound["received_at"])
        latest_inbound_received_at = (
            _coerce_utc(latest_inbound["received_at"]) if latest_inbound is not None else None
        )
        if (
            latest_inbound_received_at is not None
            and latest_inbound_received_at >= outbound_received_at
        ):
            results.append(
                FollowupScanResult(
                    thread_id=thread_id,
                    action="skipped",
                    reason="reply_received_after_outbound",
                )
            )
            continue

        due_at = add_business_days(
            outbound_received_at,
            business_days=config.default_follow_up_business_days,
        )
        if due_at > scan_time:
            results.append(
                FollowupScanResult(
                    thread_id=thread_id,
                    action="skipped",
                    reason="not_due_yet",
                )
            )
            continue

        pending_tasks = [
            task
            for task in runtime.list_scheduled_tasks_for_thread(thread_id=thread_id)
            if task["task_type"] == "followup" and task["status"] == "pending"
        ]
        if pending_tasks:
            results.append(
                FollowupScanResult(
                    thread_id=thread_id,
                    action="skipped",
                    reason="pending_followup_exists",
                )
            )
            continue

        task = runtime.create_scheduled_task(
            thread_id=thread_id,
            task_type="followup",
            created_by="system",
            due_at=due_at,
            reason="followup_due",
        )
        results.append(
            FollowupScanResult(
                thread_id=thread_id,
                action="enqueued",
                reason="followup_due",
                task_id=int(task["id"]),
            )
        )

    return results


def add_business_days(
    start_at: datetime,
    *,
    business_days: int,
) -> datetime:
    current = _coerce_utc(start_at)
    remaining = max(business_days, 0)
    while remaining > 0:
        current = current + timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
