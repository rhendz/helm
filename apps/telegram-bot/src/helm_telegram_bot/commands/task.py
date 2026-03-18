from __future__ import annotations

import asyncio
import functools

import structlog

try:
    from ddtrace import tracer as _ddtracer

    def _trace(name: str, resource: str):  # type: ignore[return]
        return _ddtracer.trace(name, resource=resource)

except ImportError:  # ddtrace not installed (e.g. CI without dev extras)
    from contextlib import contextmanager

    @contextmanager  # type: ignore[misc]
    def _trace(name: str, resource: str):
        yield

from helm_llm.client import LLMClient
from helm_orchestration import PastEventError, TaskSemantics
from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

logger = structlog.get_logger()
_service = TelegramWorkflowStatusService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message or not context.args:
        await update.message.reply_text("Usage: /task <description>")
        return
    task_text = " ".join(context.args)
    user_id = str(update.effective_user.id)
    chat_id = str(update.message.chat_id)

    # Persist run immediately (crash-safe)
    run_info = _service.start_task_run(
        request_text=task_text, submitted_by=f"telegram:{user_id}", chat_id=chat_id
    )
    run_id = run_info["id"]

    # Ack immediately
    await update.message.reply_text(f"Task received — analyzing… (run {run_id})")

    # Background: inference + orchestration + push outcome
    context.application.create_task(
        _run_task_async(update, task_text, run_id),
        update=update,
    )


async def _run_task_async(update: Update, task_text: str, run_id: int) -> None:
    try:
        with _trace("helm.task.run", resource="task_quick_add"):
            loop = asyncio.get_event_loop()
            client = LLMClient()
            with _trace("helm.task.inference", resource="infer_task_semantics"):
                semantics: TaskSemantics | None = await loop.run_in_executor(
                    None, client.infer_task_semantics, task_text
                )
            if semantics is None:
                await update.message.reply_text(
                    f"❌ Task analysis returned no result for run {run_id}. The task is saved — retry with /task."
                )
                return

            result = await loop.run_in_executor(
                None,
                functools.partial(
                    _service.execute_task_run,
                    run_id,
                    semantics=semantics,
                    request_text=task_text,
                ),
            )

            needs_action = result.get("needs_action", False)
            approval_checkpoint = result.get("approval_checkpoint")

            logger.info(
                "task_execution_complete",
                run_id=run_id,
                status=result.get("status"),
                needs_action=needs_action,
            )

            if needs_action and approval_checkpoint:
                artifact_id = approval_checkpoint.get("target_artifact_id")
                proposal_summary = approval_checkpoint.get("proposal_summary", "")
                await update.message.reply_text(
                    f"⏳ Schedule proposal ready (run {run_id})\n"
                    f"{proposal_summary}\n"
                    f"Type /approve {run_id} {artifact_id} to confirm."
                )
            else:
                await update.message.reply_text(
                    f"✅ Task scheduled (run {run_id})."
                )

    except PastEventError as exc:
        logger.warning("task_execution_past_time", run_id=run_id, reason=str(exc))
        await update.message.reply_text(
            f"⏰ The requested time is in the past for run {run_id}. "
            "Please specify a future date/time and try again."
        )
    except Exception:
        logger.exception("task_execution_failed", run_id=run_id)
        await update.message.reply_text(
            f"❌ Task execution failed for run {run_id}. The task is saved — retry with /task or check /status."
        )
