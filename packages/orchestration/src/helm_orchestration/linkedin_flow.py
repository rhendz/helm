from dataclasses import dataclass

from helm_storage.db import SessionLocal
from helm_storage.repositories.linkedin_triage import SQLAlchemyLinkedInTriageRepository
from sqlalchemy.orm import Session, sessionmaker


@dataclass(slots=True, frozen=True)
class LinkedInTriageResult:
    scanned_messages: int
    created_opportunities: int
    created_drafts: int
    workflow_status: str


def run_linkedin_triage_workflow(
    *,
    limit: int = 25,
    session_factory: sessionmaker[Session] = SessionLocal,
) -> LinkedInTriageResult:
    with session_factory() as session:
        repository = SQLAlchemyLinkedInTriageRepository(session)
        messages = repository.list_recent_messages(limit=limit)

        created_opportunities = 0
        created_drafts = 0
        for message in messages:
            source_id = f"linkedin:{message.provider_message_id}"
            if repository.get_opportunity_by_source(source_id=source_id) is None:
                repository.create_opportunity(
                    source_id=source_id,
                    company="(unknown)",
                    role_title="LinkedIn conversation follow-up",
                )
                created_opportunities += 1

            if repository.get_latest_linkedin_draft_for_thread(thread_id=message.thread_id) is None:
                repository.create_linkedin_draft(
                    thread_id=message.thread_id,
                    text=_build_draft_stub(sender_name=message.sender_name),
                )
                created_drafts += 1

        repository.commit()
        return LinkedInTriageResult(
            scanned_messages=len(messages),
            created_opportunities=created_opportunities,
            created_drafts=created_drafts,
            workflow_status="completed",
        )


def _build_draft_stub(*, sender_name: str) -> str:
    cleaned_sender = sender_name.strip() or "there"
    return (
        f"Hi {cleaned_sender},\\n\\n"
        "Thanks for reaching out on LinkedIn. Happy to continue the conversation. "
        "Could you share details on role scope, team, and timeline?\\n\\n"
        "Best,\\nAnkush"
    )
