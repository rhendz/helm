from __future__ import annotations

from app.engine.artifact_writer import write_session_artifact
from app.engine.checkin import answer_checkin, start_checkin
from app.engine.reviewer import apply_review_outcome
from app.engine.rules import apply_miss, now_utc, session_is_expired
from app.engine.session_runner import (
    recommend_for_today,
    start_session,
    validate_active_session,
)
from app.storage.files import (
    clear_active_session,
    list_course_states,
    load_active_session,
    load_course_pack,
    load_course_state,
    resolve_user_id_for_telegram,
    save_course_state,
    save_session_record,
)
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes


def register_handlers(application, llm_client) -> None:
    application.add_handler(CommandHandler("today", today_handler))
    application.add_handler(CommandHandler("start_session", start_session_handler(llm_client)))
    application.add_handler(CommandHandler("answer", answer_handler(llm_client)))
    application.add_handler(CommandHandler("miss", miss_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("checkin", checkin_handler(llm_client)))


async def today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _resolve_user_id(update)
    recommendation = recommend_for_today(user_id, persist_audit=True)
    winning = ", ".join(recommendation.audit.winning_factors) if recommendation.audit else "n/a"
    await update.message.reply_text(
        "Today:\n"
        f"Course: {recommendation.course_title}\n"
        f"Topic: {recommendation.topic_name}\n"
        f"Mode: {recommendation.mode}\n"
        f"Stage: {recommendation.policy_stage}\n"
        f"Reason: {recommendation.reason}\n"
        f"Winning factors: {winning}\n"
        "Breakdown:\n"
        f"- course_priority: {recommendation.breakdown.course_priority:.2f}\n"
        f"- due_review: {recommendation.breakdown.due_review:.2f}\n"
        f"- recovery_pressure: {recommendation.breakdown.recovery_pressure:.2f}\n"
        "- consolidation_pressure: "
        f"{recommendation.breakdown.consolidation_pressure:.2f}\n"
        f"- advancement_pressure: {recommendation.breakdown.advancement_pressure:.2f}\n"
        "- recent_performance_pressure: "
        f"{recommendation.breakdown.recent_performance_pressure:.2f}\n"
        f"- miss_pressure: {recommendation.breakdown.miss_pressure:.2f}\n"
        f"- progression_bonus: {recommendation.breakdown.progression_bonus:.2f}\n"
        f"- prerequisite_penalty: {recommendation.breakdown.prerequisite_penalty:.2f}\n"
        f"- cooldown_penalty: {recommendation.breakdown.cooldown_penalty:.2f}\n"
        f"- total: {recommendation.breakdown.total:.2f}"
    )


def start_session_handler(llm_client):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = _resolve_user_id(update)
        action = context.args[0].lower() if context.args else None
        if action not in {None, "resume", "restart", "abandon"}:
            await update.message.reply_text(
                "Use /start_session, /start_session restart, or /start_session abandon."
            )
            return

        session, message = start_session(user_id, llm_client, action=action)
        if session is None:
            await update.message.reply_text(message)
            return

        await update.message.reply_text(
            f"{message}\n"
            f"Course: {session.course_title}\n"
            f"Topic: {session.topic_name}\n"
            f"Mode: {session.mode}\n"
            f"Stage: {session.policy_stage}\n"
            f"Session status: {session.status}\n"
            f"Expires at: {session.expires_at}"
        )
        await update.message.reply_text(f"Teach:\n{session.teaching_text}")
        await update.message.reply_text(f"Quiz:\n{session.quiz_text}")

    return handler


def answer_handler(llm_client):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = _resolve_user_id(update)
        answer_text = " ".join(context.args).strip()
        if not answer_text:
            await update.message.reply_text("Use /answer <your response>.")
            return

        active, record, error = validate_active_session(user_id)
        if error:
            await update.message.reply_text(error)
            return

        course = load_course_state(user_id, active.course_id)
        previous_topic = next(
            topic for topic in course.topics if topic.id == active.topic_id
        ).model_copy()
        pack = load_course_pack(active.course_id)
        review = llm_client.review_answer(
            f"Course: {active.course_title}\n"
            f"Topic: {active.topic_name}\n"
            f"Policy stage: {active.policy_stage}\n"
            f"Mode: {active.mode}\n\n"
            f"Teaching content:\n{active.teaching_text}\n\n"
            f"Quiz:\n{active.quiz_text}\n\n"
            f"Rubric:\n{pack['rubric']}\n\n"
            f"User answer:\n{answer_text}"
        )
        course, record = apply_review_outcome(
            course,
            active.topic_id,
            record,
            review,
            now=now_utc(),
        )
        save_course_state(user_id, course)
        save_session_record(user_id, record)
        topic = next(topic for topic in course.topics if topic.id == active.topic_id)
        artifact_path = write_session_artifact(
            user_id,
            course,
            topic,
            record,
            review,
            previous_topic=previous_topic,
        )
        clear_active_session(user_id)
        await update.message.reply_text(
            f"What was right:\n{review.what_was_right}\n\n"
            f"What was missing:\n{review.what_was_missing}\n\n"
            f"Stronger answer:\n{review.stronger_answer_guidance}\n\n"
            f"Weak areas: {', '.join(review.weak_signals) if review.weak_signals else 'None'}\n"
            f"Next step: {review.next_step}\n"
            f"Artifact: {artifact_path}"
        )

    return handler


async def miss_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _resolve_user_id(update)
    reason = " ".join(context.args).strip()
    if not reason:
        await update.message.reply_text("Use /miss <reason>.")
        return

    recommendation = recommend_for_today(user_id, persist_audit=True)
    course = load_course_state(user_id, recommendation.course_id)
    course = apply_miss(course, recommendation.topic_id, reason, now=now_utc())
    save_course_state(user_id, course)
    await update.message.reply_text(
        f"Miss recorded for {course.title} / {recommendation.topic_name}. "
        "Reason saved. Pressure increased."
    )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _resolve_user_id(update)
    courses = list_course_states(user_id)
    recommendation = recommend_for_today(user_id, persist_audit=True)
    lines = [
        "Priority now: "
        f"{recommendation.course_title} / {recommendation.topic_name} "
        f"({recommendation.mode}, {recommendation.policy_stage})"
    ]
    if recommendation.audit is not None:
        lines.append("Pressure: " + ", ".join(recommendation.audit.winning_factors))
        if recommendation.audit.blocked_reasons:
            lines.append("Blocked by: " + ", ".join(recommendation.audit.blocked_reasons))
    active = load_active_session(user_id)
    if active is not None:
        stale = session_is_expired(active, now_utc())
        lines.append(
            f"Active session: {active.course_title} / {active.topic_name} "
            f"({active.status}, {'stale' if stale else 'active'})"
        )
    for course in courses:
        weakest = sorted(course.topics, key=lambda item: item.mastery)[:2]
        upcoming = sorted(
            [topic for topic in course.topics if topic.next_review],
            key=lambda item: item.next_review,
        )[:2]
        lines.append(
            f"{course.title}: scheduled {course.adherence.scheduled}, "
            f"full {course.adherence.completed_full}, lite {course.adherence.completed_lite}, "
            f"missed {course.adherence.missed}, abandoned {course.adherence.abandoned}, "
            f"miss streak {course.adherence.miss_streak}"
        )
        lines.append(
            "Weakest: " + ", ".join(f"{topic.name} ({topic.mastery:.2f})" for topic in weakest)
        )
        lines.append(
            "Upcoming reviews: "
            + ", ".join(f"{topic.name} ({topic.next_review})" for topic in upcoming)
        )
    await update.message.reply_text("\n".join(lines))


def checkin_handler(llm_client):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = _resolve_user_id(update)
        response = " ".join(context.args).strip()
        if not response:
            state = start_checkin(user_id)
            if state.status == "awaiting_approval":
                await update.message.reply_text(
                    "Weekly check-in is awaiting approval.\n"
                    "Reply with /checkin apply to persist changes or "
                    "/checkin cancel to discard them."
                )
                return
            await update.message.reply_text(
                "Weekly check-in started.\nReply with /checkin <your answer>.\n\n"
                f"Question 1: {state.questions[state.current_index]}"
            )
            return

        completed, message = answer_checkin(user_id, response, llm_client)
        await update.message.reply_text(message)
        if completed:
            return

    return handler


def _resolve_user_id(update: Update) -> str:
    telegram_user = update.effective_user
    if telegram_user is None:
        raise RuntimeError("Telegram user is required for study-agent commands")
    full_name = telegram_user.full_name or telegram_user.username or str(telegram_user.id)
    return resolve_user_id_for_telegram(telegram_user.id, full_name)
