from __future__ import annotations

import os

from helm_observability.logging import get_logger
from helm_providers.gmail import GmailProvider
from helm_runtime.email_agent import build_email_agent_runtime
from helm_storage.db import SessionLocal
from helm_storage.repositories.users import get_user_by_telegram_id
from helm_worker.jobs.email_message_ingest import process_inbound_messages
from sqlalchemy.orm import Session

logger = get_logger("helm_worker.jobs.email_reconciliation_sweep")


def _resolve_bootstrap_user_id(db: Session) -> int:
    """Look up the single bootstrap user from the TELEGRAM_ALLOWED_USER_ID env var.

    # TODO: V1 single-user workaround — in multi-user future, the job needs to
    # know which user's credentials to use without relying on a global env var.
    """
    telegram_user_id_str = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
    if not telegram_user_id_str:
        raise RuntimeError(
            "Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set"
        )
    user = get_user_by_telegram_id(int(telegram_user_id_str), db)
    if user is None:
        raise RuntimeError(
            f"Bootstrap user not found: no user with telegram_user_id={telegram_user_id_str}"
        )
    return user.id


def _build_gmail_provider(db: Session, user_id: int) -> GmailProvider:
    """Construct a GmailProvider for the given user and log construction."""
    provider = GmailProvider(user_id, db)
    logger.info("gmail_provider_constructed", user_id=user_id, source="db_credentials")
    return provider


def run() -> None:
    runtime = build_email_agent_runtime()
    config = runtime.get_email_agent_config()
    with SessionLocal() as session:
        user_id = _resolve_bootstrap_user_id(session)
        provider = _build_gmail_provider(session, user_id)
        report = provider.pull_new_messages_report()
    logger.info(
        "email_reconciliation_sweep_tick",
        count=len(report.messages),
        normalization_failures=report.failure_counts,
        recovery_reason=report.recovery_reason,
        last_history_cursor=config.last_history_cursor,
        next_history_cursor=report.next_history_cursor,
    )

    ingest_report = process_inbound_messages(runtime=runtime, messages=report.messages)
    if (
        report.next_history_cursor is not None
        and report.next_history_cursor != config.last_history_cursor
    ):
        runtime.update_email_agent_config(last_history_cursor=report.next_history_cursor)

    logger.info(
        "email_reconciliation_sweep_completed",
        processed_count=ingest_report.processed_count,
        skipped_count=ingest_report.skipped_count,
        next_history_cursor=report.next_history_cursor,
    )
