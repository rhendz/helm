from __future__ import annotations

from dataclasses import dataclass

from email_agent.runtime import EmailAgentRuntime
from email_agent.triage import process_inbound_email_message
from email_agent.types import EmailMessage
from helm_connectors.gmail import NormalizedGmailMessage
from helm_observability.logging import get_logger

logger = get_logger("helm_worker.jobs.email_message_ingest")


@dataclass(slots=True, frozen=True)
class InboundMessageIngestReport:
    processed_count: int
    skipped_count: int


def process_inbound_messages(
    *,
    runtime: EmailAgentRuntime,
    messages: list[NormalizedGmailMessage],
) -> InboundMessageIngestReport:
    processed_count = 0
    skipped_count = 0

    for message in messages:
        existing = runtime.get_message_by_provider_message_id(message.provider_message_id)
        if existing is not None and existing.processed_at is not None:
            skipped_count += 1
            continue

        result = process_inbound_email_message(
            EmailMessage(
                provider_message_id=message.provider_message_id,
                provider_thread_id=message.provider_thread_id,
                from_address=message.from_address,
                subject=message.subject,
                body_text=message.body_text,
                received_at=message.received_at,
                normalized_at=message.normalized_at,
                source=message.source,
            ),
            runtime=runtime,
        )
        processed_count += 1
        logger.info(
            "email_triage_scaffold_result",
            message_id=result.message_id,
            trigger_family=result.trigger_family,
            classification=result.classification,
            priority_score=result.priority_score,
            workflow_status=result.workflow_status,
        )

    return InboundMessageIngestReport(
        processed_count=processed_count,
        skipped_count=skipped_count,
    )
