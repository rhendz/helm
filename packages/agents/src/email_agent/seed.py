from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime
from email_agent.triage import build_email_triage_graph, run_email_triage_workflow
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


@dataclass(slots=True, frozen=True)
class SeedThreadEnvelope:
    decision: SeedThreadDecision
    messages: tuple[EmailMessage, ...]


def plan_seed_threads(messages: list[EmailMessage]) -> list[SeedThreadDecision]:
    return [envelope.decision for envelope in _build_seed_envelopes(messages)]


def build_seed_thread_envelopes(messages: list[EmailMessage]) -> list[SeedThreadEnvelope]:
    return _build_seed_envelopes(messages)


def enqueue_deep_seed_threads(
    *,
    source_type: str,
    messages: list[EmailMessage],
    runtime: EmailAgentRuntime,
) -> dict[str, object]:
    decisions = _build_seed_envelopes(messages)
    summary = summarize_seed_plan([envelope.decision for envelope in decisions])
    enqueued_count = 0
    skipped_count = 0
    queued_thread_ids: list[str] = []

    try:
        for envelope in decisions:
            if envelope.decision.bucket != "deep_seed":
                continue
            _record, created = runtime.enqueue_deep_seed_thread(
                source_type=source_type,
                provider_thread_id=envelope.decision.provider_thread_id,
                seed_reason=envelope.decision.reason,
                message_count=envelope.decision.message_count,
                latest_received_at=envelope.decision.latest_received_at,
                sample_subject=envelope.decision.sample_subject,
                from_addresses=envelope.decision.from_addresses,
                thread_payload=[
                    {
                        "provider_message_id": message.provider_message_id,
                        "provider_thread_id": message.provider_thread_id,
                        "from_address": message.from_address,
                        "subject": message.subject,
                        "body_text": message.body_text,
                        "received_at": message.received_at.isoformat(),
                        "normalized_at": message.normalized_at.isoformat(),
                        "source": message.source,
                    }
                    for message in envelope.messages
                ],
            )
            if created:
                enqueued_count += 1
                queued_thread_ids.append(envelope.decision.provider_thread_id)
            else:
                skipped_count += 1
    except SQLAlchemyError:
        summary["status"] = "unavailable"
        summary["enqueued_count"] = 0
        summary["skipped_count"] = 0
        summary["queued_thread_ids"] = []
        return summary

    summary["enqueued_count"] = enqueued_count
    summary["skipped_count"] = skipped_count
    summary["queued_thread_ids"] = queued_thread_ids
    return summary


def run_pending_deep_seed_queue(
    *,
    runtime: EmailAgentRuntime,
    limit: int = 10,
) -> list[dict[str, object]]:
    graph = build_email_triage_graph()
    results: list[dict[str, object]] = []
    pending = runtime.list_deep_seed_queue(status="pending", limit=limit)
    for item in pending:
        processing = runtime.mark_deep_seed_item_processing(item["id"])
        if processing is None or processing["status"] != "processing":
            continue
        email_thread_id: int | None = None
        try:
            for message_payload in processing["thread_payload"]:
                message = _message_from_payload(message_payload)
                result = run_email_triage_workflow(
                    message,
                    graph=graph,
                    runtime=runtime,
                    trigger_family="deep_seed",
                )
                email_thread_id = result.email_thread_id
            completed = runtime.mark_deep_seed_item_completed(
                processing["id"],
                email_thread_id=email_thread_id,
                completed_at=datetime.now(tz=UTC),
            )
            if completed is not None:
                results.append(completed)
        except Exception as exc:  # noqa: BLE001
            failed = runtime.mark_deep_seed_item_failed(
                processing["id"],
                error_message=str(exc),
            )
            if failed is not None:
                results.append(failed)
    return results


def _build_seed_envelopes(messages: list[EmailMessage]) -> list[SeedThreadEnvelope]:
    grouped: dict[str, list[EmailMessage]] = defaultdict(list)
    for message in messages:
        grouped[message.provider_thread_id].append(message)

    decisions: list[SeedThreadEnvelope] = []
    for provider_thread_id, thread_messages in grouped.items():
        ordered = sorted(
            thread_messages,
            key=lambda item: (item.received_at, item.provider_message_id),
        )
        latest = ordered[-1]
        bucket, reason = _classify_seed_bucket(ordered)
        decisions.append(
            SeedThreadEnvelope(
                decision=SeedThreadDecision(
                    provider_thread_id=provider_thread_id,
                    bucket=bucket,
                    reason=reason,
                    message_count=len(ordered),
                    latest_received_at=latest.received_at,
                    sample_subject=latest.subject,
                    from_addresses=tuple(sorted({item.from_address for item in ordered})),
                ),
                messages=tuple(ordered),
            )
        )

    return sorted(
        decisions,
        key=lambda item: (
            item.decision.latest_received_at,
            item.decision.provider_thread_id,
        ),
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


def _message_from_payload(payload: dict[str, object]) -> EmailMessage:
    return EmailMessage(
        provider_message_id=str(payload["provider_message_id"]),
        provider_thread_id=str(payload["provider_thread_id"]),
        from_address=str(payload["from_address"]),
        subject=str(payload.get("subject") or ""),
        body_text=str(payload.get("body_text") or ""),
        received_at=datetime.fromisoformat(str(payload["received_at"])),
        normalized_at=datetime.fromisoformat(str(payload["normalized_at"])),
        source=str(payload.get("source") or "gmail"),
    )
