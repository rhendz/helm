from datetime import UTC, datetime

from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.guards import is_allowed_user


def parse_single_id_arg(args: list[str]) -> int | None:
    if len(args) != 1:
        return None
    raw_value = args[0].strip()
    if not raw_value:
        return None
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def parse_two_arg_task_inputs(args: list[str]) -> tuple[int, str] | None:
    if len(args) != 2:
        return None
    thread_id = parse_single_id_arg([args[0]])
    if thread_id is None:
        return None
    due_at = args[1].strip()
    if not due_at:
        return None
    return thread_id, due_at


def parse_iso_datetime_arg(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


async def reject_if_unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if is_allowed_user(update):
        return False
    if update.message:
        await update.message.reply_text("Unauthorized user.")
    return True
