import logging

from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import parse_single_id_arg, reject_if_unauthorized
from helm_telegram_bot.formatters import sync_events
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

logger = logging.getLogger(__name__)

_service = TelegramWorkflowStatusService()


def _next_actions(run: dict[str, object]) -> list[str]:
    labels: list[str] = []
    for key in ("available_actions", "safe_next_actions"):
        actions = run.get(key, [])
        if not isinstance(actions, list):
            continue
        for item in actions:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            if isinstance(action, str) and action not in labels:
                labels.append(action)
    return labels


def _format_run(run: dict[str, object]) -> str:
    step = run.get("current_step") or "n/a"
    paused_state = run.get("paused_state") or "active"
    last_event = run.get("last_event_summary") or "No recent event."
    actions = _next_actions(run)
    next_action = ", ".join(actions) if actions else "none"
    lines = [
        f"Run {run['id']} [{run['status']}] step={step} paused={paused_state}\n"
        f"Last: {last_event}\n"
        f"Needs action: {'yes' if run.get('needs_action') else 'no'} | Next: {next_action}"
    ]
    completion_summary = run.get("completion_summary")
    if isinstance(completion_summary, dict):
        headline = completion_summary.get("headline")
        if isinstance(headline, str) and headline:
            lines.append(f"Outcome: {headline}")
        scheduled_highlights = completion_summary.get("scheduled_highlights")
        if isinstance(scheduled_highlights, list) and scheduled_highlights:
            lines.append("Scheduled: " + ", ".join(str(item) for item in scheduled_highlights[:3]))
        if completion_summary.get("total_sync_writes"):
            lines.append(
                "Sync: "
                f"{completion_summary.get('total_sync_writes')} writes "
                f"({completion_summary.get('task_sync_writes')} task, "
                f"{completion_summary.get('calendar_sync_writes')} calendar) "
                f"status={completion_summary.get('downstream_sync_status') or 'n/a'}"
            )
        carry_forward = completion_summary.get("carry_forward_tasks")
        if isinstance(carry_forward, list) and carry_forward:
            lines.append(f"Carry forward: {', '.join(str(item) for item in carry_forward[:3])}")
        attention_items = completion_summary.get("attention_items")
        if isinstance(attention_items, list) and attention_items:
            lines.append(f"Attention: {'; '.join(str(item) for item in attention_items[:3])}")

    # Append sync timeline if available
    run_id = run.get("id")
    if isinstance(run_id, int):
        try:
            sync_event_list = _service.list_sync_events(run_id)
            if sync_event_list:
                sync_timeline = sync_events.format_sync_timeline(sync_event_list, max_events=8)
                if sync_timeline:
                    lines.append(f"Sync timeline:\n{sync_timeline}")
                    logger.debug(
                        "workflow_command_invoked",
                        extra={
                            "run_id": run_id,
                            "command": "workflows_detail",
                            "sync_record_count": len(sync_event_list),
                        },
                    )
        except Exception:
            logger.exception("sync_timeline_fetch_error", extra={"run_id": run_id})

    approval_checkpoint = run.get("approval_checkpoint")
    if isinstance(approval_checkpoint, dict):
        proposal_summary = (
            approval_checkpoint.get("proposal_summary") or "Proposal summary unavailable."
        )
        target_artifact_id = approval_checkpoint.get("target_artifact_id")
        target_version_number = approval_checkpoint.get("target_version_number")
        lines.append(
            f"Latest proposal: v{target_version_number} artifact={target_artifact_id}\n"
            "Proposal: "
            f"{proposal_summary}\n"
            "Actions: approve/reject/request_revision must name this artifact id."
        )
        for extra_line in _proposal_detail_lines(approval_checkpoint):
            lines.append(extra_line)
    latest_proposal = run.get("latest_proposal_version")
    if (
        isinstance(latest_proposal, dict)
        and approval_checkpoint is None
        and not isinstance(completion_summary, dict)
    ):
        lines.append(
            f"Latest proposal: v{latest_proposal.get('version_number')} "
            f"artifact={latest_proposal.get('artifact_id')}"
        )
        for extra_line in _proposal_detail_lines(latest_proposal):
            lines.append(extra_line)
    latest_decision = run.get("latest_decision")
    if isinstance(latest_decision, dict):
        decision = latest_decision.get("decision")
        actor = latest_decision.get("actor")
        target = latest_decision.get("target_artifact_id")
        lines.append(f"Latest decision: {decision} by {actor} on artifact {target}")
    proposal_versions = run.get("proposal_versions")
    if isinstance(proposal_versions, list) and len(proposal_versions) > 1:
        version_labels = []
        for item in proposal_versions[:3]:
            if not isinstance(item, dict):
                continue
            status = "current"
            if item.get("approved"):
                status = "approved"
            elif item.get("rejected"):
                status = "rejected"
            elif item.get("superseded"):
                status = "superseded"
            version_labels.append(f"v{item.get('version_number')}:{status}")
        if version_labels:
            lines.append(f"History: {', '.join(version_labels)}")
    return "\n".join(lines)


def _proposal_detail_lines(proposal: dict[str, object]) -> list[str]:
    lines: list[str] = []
    time_blocks = proposal.get("time_blocks")
    if isinstance(time_blocks, list) and time_blocks:
        preview = []
        for block in time_blocks[:2]:
            if not isinstance(block, dict):
                continue
            preview.append(f"{block.get('title')} [{block.get('start')} -> {block.get('end')}]")
        if preview:
            lines.append(f"Blocks: {'; '.join(preview)}")
    for key, label in (
        ("honored_constraints", "Constraints"),
        ("assumptions", "Assumptions"),
        ("carry_forward_tasks", "Carry forward"),
        ("proposed_changes", "Planned changes"),
    ):
        items = proposal.get(key)
        if isinstance(items, list) and items:
            lines.append(f"{label}: {', '.join(str(item) for item in items[:3])}")
    return lines


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


async def replay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    reason = " ".join(context.args[1:]).strip()
    if run_id is None or not reason:
        await update.message.reply_text("Usage: /workflow_replay <run_id> <reason>")
        return
    result = _service.request_replay(
        run_id,
        actor=f"telegram:{update.effective_user.id}",
        reason=reason,
    )
    await update.message.reply_text(_format_run(result))


async def versions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    if run_id is None:
        await update.message.reply_text("Usage: /workflow_versions <run_id>")
        return
    detail = _service.get_run_detail(run_id)
    if detail is None:
        await update.message.reply_text(f"Workflow run {run_id} not found.")
        return
    proposal_versions = detail.get("proposal_versions", [])
    if not proposal_versions:
        await update.message.reply_text(f"Run {run_id} has no schedule proposal versions.")
        return
    lines = [f"Run {run_id} proposal versions:"]
    for item in proposal_versions:
        if not isinstance(item, dict):
            continue
        status = "current"
        if item.get("approved"):
            status = "approved"
        elif item.get("rejected"):
            status = "rejected"
        elif item.get("superseded"):
            status = "superseded"
        feedback = item.get("revision_feedback_summary")
        line = f"v{item.get('version_number')} artifact={item.get('artifact_id')} {status}"
        if feedback:
            line += f" | feedback: {feedback}"
        lines.append(line)
    await update.message.reply_text("\n".join(lines))


async def sync_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display full sync event timeline for a workflow run."""
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args)
    if run_id is None:
        await update.message.reply_text("Usage: /workflow_sync_detail <run_id>")
        return
    
    # Fetch full sync details
    try:
        sync_details = _service.get_sync_details(run_id)
        sync_event_list = sync_details.get("sync_records", [])
        
        if not sync_event_list:
            await update.message.reply_text(f"No sync events for workflow run {run_id}.")
            logger.debug(
                "workflow_command_invoked",
                extra={
                    "run_id": run_id,
                    "command": "workflow_sync_detail",
                    "sync_record_count": 0,
                },
            )
            return
        
        # Format full timeline (use large max_events to show all available)
        sync_timeline = sync_events.format_sync_timeline(sync_event_list, max_events=999)
        if not sync_timeline:
            await update.message.reply_text(f"No sync events for workflow run {run_id}.")
            return
        
        # Build response with summary and timeline
        lines = [
            f"Run {run_id} sync timeline:",
            f"Total writes: {sync_details.get('total_sync_writes', 0)} "
            f"(task: {sync_details.get('task_sync_writes', 0)}, "
            f"calendar: {sync_details.get('calendar_sync_writes', 0)})",
            "",
            sync_timeline,
        ]
        
        response = "\n".join(lines)
        await update.message.reply_text(response)
        
        logger.debug(
            "workflow_command_invoked",
            extra={
                "run_id": run_id,
                "command": "workflow_sync_detail",
                "sync_record_count": len(sync_event_list),
            },
        )
    except Exception as e:
        logger.exception("sync_detail_command_error", extra={"run_id": run_id, "error": str(e)})
        await update.message.reply_text(f"Error fetching sync details for run {run_id}. See logs for details.")
