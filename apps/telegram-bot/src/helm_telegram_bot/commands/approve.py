import structlog
from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import parse_single_id_arg, reject_if_unauthorized
from helm_telegram_bot.commands.workflows import _format_run
from helm_telegram_bot.services.command_service import TelegramCommandService
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

logger = structlog.get_logger()
_draft_service = TelegramCommandService()
_workflow_service = TelegramWorkflowStatusService()
_service = _draft_service


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await approve(update, context)


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Usage: /approve <id>")
        return
    if len(context.args) == 1:
        draft_id = parse_single_id_arg(context.args)
        if draft_id is None:
            await update.message.reply_text("Usage: /approve <id>")
            return
        result = _service.approve_draft(draft_id)
        await update.message.reply_text(result.message)
        return

    run_id = parse_single_id_arg(context.args[:1])
    target_artifact_id = parse_single_id_arg(context.args[1:2])
    if run_id is None or target_artifact_id is None:
        await update.message.reply_text(
            "Usage: /approve <id> or /approve <run_id> <proposal_artifact_id>"
        )
        return
    result = _workflow_service.approve_run(
        run_id,
        actor=f"telegram:{update.effective_user.id}",
        target_artifact_id=target_artifact_id,
    )
    await update.message.reply_text(_format_run(result))
    # Trigger immediate execution of apply_schedule step
    try:
        _workflow_service.execute_after_approval(run_id)
        await update.message.reply_text("✅ Approved and syncing to calendar…")
    except Exception:
        logger.exception("approve_inline_execution_failed", run_id=run_id)
        await update.message.reply_text(
            f"✅ Approved (run {run_id}). Calendar sync will complete shortly."
        )


async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    target_artifact_id = parse_single_id_arg(context.args[1:2])
    if run_id is None or target_artifact_id is None:
        await update.message.reply_text("Usage: /reject <run_id> <proposal_artifact_id>")
        return
    result = _workflow_service.reject_run(
        run_id,
        actor=f"telegram:{update.effective_user.id}",
        target_artifact_id=target_artifact_id,
    )
    await update.message.reply_text(_format_run(result))


async def request_revision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    target_artifact_id = parse_single_id_arg(context.args[1:2])
    feedback = " ".join(context.args[2:]).strip()
    if run_id is None or target_artifact_id is None or not feedback:
        await update.message.reply_text(
            "Usage: /request_revision <run_id> <proposal_artifact_id> <feedback>"
        )
        return
    result = _workflow_service.request_revision(
        run_id,
        actor=f"telegram:{update.effective_user.id}",
        target_artifact_id=target_artifact_id,
        feedback=feedback,
    )
    await update.message.reply_text(_format_run(result))
