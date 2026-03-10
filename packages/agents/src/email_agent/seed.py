from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from email_agent.types import EmailMessage


@dataclass(slots=True, frozen=True)
class SeedThreadDecision:
    provider_thread_id: str
    bucket: str
    reason: str
    message_count: int
    latest_received_at: datetime
    sample_subject: str
    from_addresses: tuple[str, ...]


def plan_seed_threads(messages: list[EmailMessage]) -> list[SeedThreadDecision]:
    grouped: dict[str, list[EmailMessage]] = defaultdict(list)
    for message in messages:
        grouped[message.provider_thread_id].append(message)

    decisions: list[SeedThreadDecision] = []
    for provider_thread_id, thread_messages in grouped.items():
        ordered = sorted(
            thread_messages,
            key=lambda item: (item.received_at, item.provider_message_id),
        )
        latest = ordered[-1]
        bucket, reason = _classify_seed_bucket(ordered)
        decisions.append(
            SeedThreadDecision(
                provider_thread_id=provider_thread_id,
                bucket=bucket,
                reason=reason,
                message_count=len(ordered),
                latest_received_at=latest.received_at,
                sample_subject=latest.subject,
                from_addresses=tuple(sorted({item.from_address for item in ordered})),
            )
        )

    return sorted(
        decisions,
        key=lambda item: (item.latest_received_at, item.provider_thread_id),
        reverse=True,
    )


def summarize_seed_plan(decisions: list[SeedThreadDecision]) -> dict[str, object]:
    bucket_counts = {
        "deep_seed": 0,
        "light_seed_only": 0,
        "do_not_surface": 0,
    }
    bucket_thread_ids = {
        "deep_seed": [],
        "light_seed_only": [],
        "do_not_surface": [],
    }
    for decision in decisions:
        bucket_counts[decision.bucket] += 1
        bucket_thread_ids[decision.bucket].append(decision.provider_thread_id)

    return {
        "status": "accepted",
        "thread_count": len(decisions),
        "bucket_counts": bucket_counts,
        "bucket_thread_ids": bucket_thread_ids,
        "decisions": [
            {
                "provider_thread_id": decision.provider_thread_id,
                "bucket": decision.bucket,
                "reason": decision.reason,
                "message_count": decision.message_count,
                "latest_received_at": decision.latest_received_at,
                "sample_subject": decision.sample_subject,
                "from_addresses": list(decision.from_addresses),
            }
            for decision in decisions
        ],
    }


def _classify_seed_bucket(messages: list[EmailMessage]) -> tuple[str, str]:
    latest = messages[-1]
    subject = latest.subject.lower()
    sender = latest.from_address.lower()

    if "no-reply" in sender or any(
        token in subject for token in ("newsletter", "unsubscribe", "digest")
    ):
        return "do_not_surface", "bulk_or_low_signal"

    if len(messages) > 1:
        return "deep_seed", "multi_message_thread"

    if any(token in sender for token in ("recruiter", "jobs", "talent")):
        return "deep_seed", "sender_signal"

    if any(
        token in subject
        for token in ("urgent", "interview", "opportunity", "review", "deadline", "asap")
    ):
        return "deep_seed", "subject_signal"

    return "light_seed_only", "single_message_light_signal"
