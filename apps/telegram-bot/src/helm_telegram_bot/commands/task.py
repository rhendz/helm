from __future__ import annotations

import asyncio

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from helm_llm.client import LLMClient
from helm_orchestration import ApprovalAction, ConditionalApprovalPolicy, TaskSemantics
from helm_telegram_bot.commands.common import reject_if_unauthorized
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

logger = structlog.get_logger()
_service = TelegramWorkflowStatusService()
_policy = ConditionalApprovalPolicy()


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

    # Background: inference + policy + push outcome
    context.application.create_task(
        _run_task_async(update, task_text, run_id),
        update=update,
    )


async def _run_task_async(update: Update, task_text: str, run_id: int) -> None:
    try:
        loop = asyncio.get_event_loop()
        client = LLMClient()
        semantics: TaskSemantics = await loop.run_in_executor(
            None, client.infer_task_semantics, task_text
        )
        decision = _policy.evaluate(semantics)
        # Format outcome message
        lines = [
            f"📋 *Task Analysis* (run {run_id})",
            f"Urgency: {semantics.urgency} | Priority: {semantics.priority}",
            f"Estimated: {semantics.sizing_minutes}min | Confidence: {semantics.confidence:.0%}",
        ]
        if decision.action == ApprovalAction.APPROVE:
            lines.append("✅ Auto-approved — ready for scheduling")
        else:
            lines.append("⚠️ Needs review — approval required")
            if decision.revision_feedback:
                lines.append(f"Reason: {decision.revision_feedback}")
        await update.message.reply_text("\n".join(lines))
        logger.info(
            "task_inference_complete",
            run_id=run_id,
            urgency=semantics.urgency,
            priority=semantics.priority,
            sizing=semantics.sizing_minutes,
            confidence=semantics.confidence,
            decision=decision.action,
        )
    except Exception:
        logger.exception("task_inference_failed", run_id=run_id)
        await update.message.reply_text(
            f"❌ Task analysis failed for run {run_id}. The task is saved — retry with /task or check /status."
        )
