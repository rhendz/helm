from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import parse_single_id_arg, reject_if_unauthorized
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

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
    approval_checkpoint = run.get("approval_checkpoint")
    if isinstance(approval_checkpoint, dict):
        proposal_summary = approval_checkpoint.get("proposal_summary") or "Proposal summary unavailable."
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
    if isinstance(latest_proposal, dict) and approval_checkpoint is None:
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
