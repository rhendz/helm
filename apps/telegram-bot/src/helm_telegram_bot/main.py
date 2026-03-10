from helm_observability.logging import get_logger, setup_logging
from telegram.ext import Application, CommandHandler

from helm_telegram_bot.commands import (
    actions,
    approve,
    digest,
    done_task,
    drafts,
    followup,
    remind,
    resolve,
    review,
    reviews,
    snooze,
    start,
    study,
    tasks,
    thread,
    threads,
)
from helm_telegram_bot.config import get_settings


def main() -> None:
    setup_logging()
    logger = get_logger("helm_telegram_bot")
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start.handle))
    application.add_handler(CommandHandler("digest", digest.handle))
    application.add_handler(CommandHandler("actions", actions.handle))
    application.add_handler(CommandHandler("drafts", drafts.handle))
    application.add_handler(CommandHandler("study", study.handle))
    application.add_handler(CommandHandler("approve", approve.handle))
    application.add_handler(CommandHandler("done_task", done_task.handle))
    application.add_handler(CommandHandler("snooze", snooze.handle))
    application.add_handler(CommandHandler("remind", remind.handle))
    application.add_handler(CommandHandler("followup", followup.handle))
    application.add_handler(CommandHandler("resolve", resolve.handle))
    application.add_handler(CommandHandler("review", review.handle))
    application.add_handler(CommandHandler("reviews", reviews.handle))
    application.add_handler(CommandHandler("tasks", tasks.handle))
    application.add_handler(CommandHandler("thread", thread.handle))
    application.add_handler(CommandHandler("threads", threads.handle))

    logger.info("telegram_bot_started")
    application.run_polling()


if __name__ == "__main__":
    main()
