from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import parse_single_id_arg, reject_if_unauthorized
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

_service = TelegramWorkflowStatusService()


def _format_run(run: dict[str, object]) -> str:
    step = run.get("current_step") or "n/a"
    paused_state = run.get("paused_state") or "active"
    last_event = run.get("last_event_summary") or "No recent event."
    actions = [item["action"] for item in run.get("available_actions", [])]
    next_action = ", ".join(actions) if actions else "none"
    lines = [
        f"Run {run['id']} [{run['status']}] step={step} paused={paused_state}\n"
        f"Last: {last_event}\n"
        f"Needs action: {'yes' if run.get('needs_action') else 'no'} | Next: {next_action}"
    ]
    approval_checkpoint = run.get("approval_checkpoint")
    if isinstance(approval_checkpoint, dict):
        proposal_summary = approval_checkpoint.get("proposal_summary") or "Proposal summary unavailable."
        lines.append(
            "Proposal: "
            f"{proposal_summary}\n"
            "Actions: approve continues, reject closes, request_revision regenerates."
        )
    latest_decision = run.get("latest_decision")
    if isinstance(latest_decision, dict):
        decision = latest_decision.get("decision")
        actor = latest_decision.get("actor")
        lines.append(f"Latest decision: {decision} by {actor}")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    request_text = " ".join(context.args).strip()
    if not request_text:
        await update.message.reply_text("Usage: /workflow_start <request text>")
        return
    created = _service.start_run(
        request_text=request_text,
        submitted_by=f"telegram:{update.effective_user.id}",
        chat_id=str(update.effective_user.id),
    )
    await update.message.reply_text(_format_run(created))


async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    runs = _service.list_recent_runs()
    if not runs:
        await update.message.reply_text("No workflow runs.")
        return
    await update.message.reply_text("\n\n".join(_format_run(run) for run in runs))


async def needs_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    runs = _service.list_runs_needing_action()
    if not runs:
        await update.message.reply_text("No workflow runs need action.")
        return
    await update.message.reply_text("\n\n".join(_format_run(run) for run in runs))


async def retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    reason = " ".join(context.args[1:]).strip()
    if run_id is None or not reason:
        await update.message.reply_text("Usage: /workflow_retry <run_id> <reason>")
        return
    result = _service.retry_run(run_id, reason=reason)
    await update.message.reply_text(_format_run(result))


async def terminate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    reason = " ".join(context.args[1:]).strip()
    if run_id is None or not reason:
        await update.message.reply_text("Usage: /workflow_terminate <run_id> <reason>")
        return
    result = _service.terminate_run(run_id, reason=reason)
    await update.message.reply_text(_format_run(result))
