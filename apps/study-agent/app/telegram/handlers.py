from __future__ import annotations

from datetime import date

from app.config import DEFAULT_USER_ID
from app.engine.artifact_writer import write_session_artifact
from app.engine.checkin import answer_checkin, start_checkin
from app.engine.prioritizer import choose_recommendation
from app.engine.reviewer import apply_review_to_topic, finalize_session_record
from app.engine.scheduler import next_review_date
from app.engine.session_runner import recommend_for_today, start_session
from app.storage.files import (
    clear_active_session,
    list_course_states,
    load_active_session,
    load_course_pack,
    load_course_state,
    load_session_record,
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
    recommendation = recommend_for_today(DEFAULT_USER_ID)
    await update.message.reply_text(
        f"Today:\n"
        f"Course: {recommendation.course_title}\n"
        f"Topic: {recommendation.topic_name}\n"
        f"Mode: {recommendation.mode}\n"
        f"Reason: {recommendation.reason}"
    )


def start_session_handler(llm_client):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        session = start_session(DEFAULT_USER_ID, llm_client)
        await update.message.reply_text(
            "Session started.\n"
            f"Course: {session.course_title}\n"
            f"Topic: {session.topic_name}\n"
            f"Mode: {session.mode}"
        )
        await update.message.reply_text(f"Teach:\n{session.teaching_text}")
        await update.message.reply_text(f"Quiz:\n{session.quiz_text}")

    return handler


def answer_handler(llm_client):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        answer_text = " ".join(context.args).strip()
        if not answer_text:
            await update.message.reply_text("Use /answer <your response>.")
            return

        active = load_active_session(DEFAULT_USER_ID)
        if active is None:
            await update.message.reply_text("No active session. Run /start_session first.")
            return

        record = load_session_record(DEFAULT_USER_ID, active.session_id)
        course = load_course_state(DEFAULT_USER_ID, active.course_id)
        topic = next(topic for topic in course.topics if topic.id == active.topic_id)
        pack = load_course_pack(active.course_id)
        rubric = pack["rubric"]
        review = llm_client.review_answer(
            f"Course: {active.course_title}\n"
            f"Topic: {active.topic_name}\n"
            f"Mode: {active.mode}\n\n"
            f"Teaching content:\n{active.teaching_text}\n\n"
            f"Quiz:\n{active.quiz_text}\n\n"
            f"Rubric:\n{rubric}\n\n"
            f"User answer:\n{answer_text}"
        )
        apply_review_to_topic(course, active.topic_id, review)
        record = finalize_session_record(record, review)
        course.adherence.completed += 1
        course.adherence.miss_streak = 0
        course.last_session_date = date.today().isoformat()
        save_course_state(DEFAULT_USER_ID, course)
        save_session_record(DEFAULT_USER_ID, record)
        artifact_path = write_session_artifact(DEFAULT_USER_ID, course, topic, record, review)
        clear_active_session(DEFAULT_USER_ID)
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
    reason = " ".join(context.args).strip()
    if not reason:
        await update.message.reply_text("Use /miss <reason>.")
        return

    recommendation = choose_recommendation(list_course_states(DEFAULT_USER_ID))
    course = load_course_state(DEFAULT_USER_ID, recommendation.course_id)
    topic = next(topic for topic in course.topics if topic.id == recommendation.topic_id)
    course.adherence.scheduled += 1
    course.adherence.missed += 1
    course.adherence.miss_streak += 1
    course.adherence.recent_miss_reasons.append(reason)
    course.adherence.recent_miss_reasons = course.adherence.recent_miss_reasons[-5:]
    topic.next_review = next_review_date(topic, 0.3)
    save_course_state(DEFAULT_USER_ID, course)
    await update.message.reply_text(
        f"Miss recorded for {course.title} / {topic.name}. "
        f"Reason saved. Pressure increased and the topic was pushed back into near-term review."
    )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    courses = list_course_states(DEFAULT_USER_ID)
    recommendation = choose_recommendation(courses)
    lines = [
        "Priority now: "
        f"{recommendation.course_title} / {recommendation.topic_name} "
        f"({recommendation.mode})"
    ]
    for course in courses:
        weakest = sorted(course.topics, key=lambda item: item.mastery)[:2]
        upcoming = sorted(
            [topic for topic in course.topics if topic.next_review],
            key=lambda item: item.next_review,
        )[:2]
        lines.append(
            f"{course.title}: priority {course.priority}, "
            f"adherence {course.adherence.completed}/{course.adherence.scheduled}, "
            f"missed {course.adherence.missed}, miss streak {course.adherence.miss_streak}"
        )
        lines.append(
            "Weakest: "
            + ", ".join(f"{topic.name} ({topic.mastery:.2f})" for topic in weakest)
        )
        lines.append(
            "Upcoming reviews: "
            + ", ".join(f"{topic.name} ({topic.next_review})" for topic in upcoming)
        )
    await update.message.reply_text("\n".join(lines))


def checkin_handler(llm_client):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        response = " ".join(context.args).strip()
        if not response:
            state = start_checkin(DEFAULT_USER_ID)
            await update.message.reply_text(
                "Weekly check-in started.\nReply with /checkin <your answer>.\n\n"
                f"Question 1: {state.questions[state.current_index]}"
            )
            return

        completed, message = answer_checkin(DEFAULT_USER_ID, response, llm_client)
        if completed:
            await update.message.reply_text(message)
            return
        next_index = len(load_checkin_answers(DEFAULT_USER_ID))
        await update.message.reply_text(f"Question {next_index + 1}: {message}")

    return handler


def load_checkin_answers(user_id: str) -> list[str]:
    from app.storage.files import load_active_checkin

    state = load_active_checkin(user_id)
    return [] if state is None else state.answers
