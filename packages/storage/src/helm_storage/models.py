from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from helm_storage.db import Base


class ContactORM(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    telegram_handle: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    relationship_type: Mapped[str | None] = mapped_column(String(64))
    importance_score: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActionItemORM(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DraftReplyORM(Base):
    __tablename__ = "draft_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_type: Mapped[str] = mapped_column(String(32), default="email", nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(255))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    draft_text: Mapped[str] = mapped_column(Text(), nullable=False)
    tone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DraftTransitionAuditORM(Base):
    __tablename__ = "draft_transition_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    success: Mapped[bool] = mapped_column(nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DigestItemORM(Base):
    __tablename__ = "digest_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text(), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    related_contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL")
    )
    related_action_id: Mapped[int | None] = mapped_column(
        ForeignKey("action_items.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentRunORM(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text())


class EmailMessageORM(Base):
    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    provider_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    provider_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email_thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_threads.id", ondelete="SET NULL")
    )
    source_draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_drafts.id", ondelete="SET NULL")
    )
    direction: Mapped[str] = mapped_column(String(32), default="inbound", nullable=False)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    to_addresses: Mapped[str | None] = mapped_column(Text())
    cc_addresses: Mapped[str | None] = mapped_column(Text())
    bcc_addresses: Mapped[str | None] = mapped_column(Text())
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text())
    body_text: Mapped[str] = mapped_column(Text(), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    normalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(32), default="gmail", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EmailThreadORM(Base):
    __tablename__ = "email_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    provider_thread_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    business_state: Mapped[str] = mapped_column(String(32), default="uninitialized", nullable=False)
    visible_labels: Mapped[str] = mapped_column(Text(), default="", nullable=False)
    current_summary: Mapped[str | None] = mapped_column(Text())
    latest_confidence_band: Mapped[str | None] = mapped_column(String(16))
    resurfacing_source: Mapped[str | None] = mapped_column(String(32))
    action_reason: Mapped[str | None] = mapped_column(String(32))
    last_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_messages.id", ondelete="SET NULL")
    )
    last_inbound_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_messages.id", ondelete="SET NULL")
    )
    last_outbound_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_messages.id", ondelete="SET NULL")
    )
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActionProposalORM(Base):
    __tablename__ = "action_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    email_thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id", ondelete="CASCADE"))
    proposal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text())
    confidence_band: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ClassificationArtifactORM(Base):
    __tablename__ = "classification_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    email_thread_id: Mapped[int] = mapped_column(
        ForeignKey("email_threads.id", ondelete="CASCADE")
    )
    email_message_id: Mapped[int] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE")
    )
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    business_state: Mapped[str] = mapped_column(String(32), nullable=False)
    visible_labels: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    action_reason: Mapped[str | None] = mapped_column(String(32))
    resurfacing_source: Mapped[str | None] = mapped_column(String(32))
    confidence_band: Mapped[str | None] = mapped_column(String(16))
    decision_context: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EmailDraftORM(Base):
    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    email_thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id", ondelete="CASCADE"))
    action_proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("action_proposals.id", ondelete="SET NULL")
    )
    draft_body: Mapped[str] = mapped_column(Text(), nullable=False)
    draft_subject: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="generated", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="pending_user", nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    draft_reasoning_artifact_ref: Mapped[str | None] = mapped_column(String(255))
    final_sent_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_messages.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DraftReasoningArtifactORM(Base):
    __tablename__ = "draft_reasoning_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    email_draft_id: Mapped[int] = mapped_column(
        ForeignKey("email_drafts.id", ondelete="CASCADE")
    )
    email_thread_id: Mapped[int] = mapped_column(
        ForeignKey("email_threads.id", ondelete="CASCADE")
    )
    action_proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("action_proposals.id", ondelete="SET NULL")
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_context: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    model_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    reasoning_payload: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    refinement_metadata: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EmailSendAttemptORM(Base):
    __tablename__ = "email_send_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    draft_id: Mapped[int] = mapped_column(ForeignKey("email_drafts.id", ondelete="CASCADE"))
    email_thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id", ondelete="CASCADE"))
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(Text())
    provider_error_code: Mapped[str | None] = mapped_column(String(64))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EmailDeepSeedQueueORM(Base):
    __tablename__ = "email_deep_seed_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    seed_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sample_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    from_addresses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    thread_payload: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text())
    email_thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_threads.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ScheduledThreadTaskORM(Base):
    __tablename__ = "scheduled_thread_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    email_thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id", ondelete="CASCADE"))
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    reason: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EmailAgentConfigORM(Base):
    __tablename__ = "email_agent_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_required_before_send: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    default_follow_up_business_days: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )
    last_history_cursor: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OpportunityORM(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StudySessionORM(Base):
    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text(), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class KnowledgeGapORM(Base):
    __tablename__ = "knowledge_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    source_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LearningTaskORM(Base):
    __tablename__ = "learning_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    related_gap_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_gaps.id", ondelete="SET NULL")
    )


class ReplayQueueORM(Base):
    __tablename__ = "replay_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JobControlORM(Base):
    __tablename__ = "job_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    paused: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
