from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from helm_storage.db import Base


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserCredentialsORM(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_credentials_user_provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(255))
    client_secret: Mapped[str | None] = mapped_column(String(255))
    access_token: Mapped[str | None] = mapped_column(Text())
    refresh_token: Mapped[str] = mapped_column(Text(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str | None] = mapped_column(Text())
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ContactORM(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text())


class WorkflowRunORM(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True, nullable=False
    )
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    current_step_name: Mapped[str | None] = mapped_column(String(128))
    needs_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_step_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_outcome_summary: Mapped[str | None] = mapped_column(Text())
    execution_error_summary: Mapped[str | None] = mapped_column(Text())
    blocked_reason: Mapped[str | None] = mapped_column(String(64))
    failure_class: Mapped[str | None] = mapped_column(String(64))
    retry_state: Mapped[str | None] = mapped_column(String(32))
    resume_step_name: Mapped[str | None] = mapped_column(String(128))
    resume_step_attempt: Mapped[int | None] = mapped_column(Integer)
    last_event_summary: Mapped[str | None] = mapped_column(Text())
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list["WorkflowStepORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["WorkflowArtifactORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    events: Mapped[list["WorkflowEventORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    approval_checkpoints: Mapped[list["WorkflowApprovalCheckpointORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    specialist_invocations: Mapped[list["WorkflowSpecialistInvocationORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    sync_records: Mapped[list["WorkflowSyncRecordORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class WorkflowStepORM(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_name", "attempt_number", name="uq_workflow_step_attempt"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    validation_outcome_summary: Mapped[str | None] = mapped_column(Text())
    execution_error_summary: Mapped[str | None] = mapped_column(Text())
    failure_class: Mapped[str | None] = mapped_column(String(64))
    retry_state: Mapped[str | None] = mapped_column(String(32))
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped["WorkflowRunORM"] = relationship(back_populates="steps")
    artifacts: Mapped[list["WorkflowArtifactORM"]] = relationship(back_populates="step")
    events: Mapped[list["WorkflowEventORM"]] = relationship(back_populates="step")
    specialist_invocations: Mapped[list["WorkflowSpecialistInvocationORM"]] = relationship(
        back_populates="step"
    )
    sync_records: Mapped[list["WorkflowSyncRecordORM"]] = relationship(
        back_populates="step",
        foreign_keys="WorkflowSyncRecordORM.step_id",
    )


class WorkflowArtifactORM(Base):
    __tablename__ = "workflow_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "artifact_type", "version_number", name="uq_workflow_artifact_version"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL")
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    producer_step_name: Mapped[str | None] = mapped_column(String(128))
    lineage_parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_artifacts.id", ondelete="SET NULL")
    )
    supersedes_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_artifacts.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped["WorkflowRunORM"] = relationship(back_populates="artifacts")
    step: Mapped["WorkflowStepORM | None"] = relationship(back_populates="artifacts")
    lineage_parent: Mapped["WorkflowArtifactORM | None"] = relationship(
        remote_side="WorkflowArtifactORM.id",
        foreign_keys=[lineage_parent_id],
    )
    supersedes_artifact: Mapped["WorkflowArtifactORM | None"] = relationship(
        remote_side="WorkflowArtifactORM.id",
        foreign_keys=[supersedes_artifact_id],
    )
    input_to_invocations: Mapped[list["WorkflowSpecialistInvocationORM"]] = relationship(
        back_populates="input_artifact",
        foreign_keys="WorkflowSpecialistInvocationORM.input_artifact_id",
    )
    output_from_invocations: Mapped[list["WorkflowSpecialistInvocationORM"]] = relationship(
        back_populates="output_artifact",
        foreign_keys="WorkflowSpecialistInvocationORM.output_artifact_id",
    )
    approval_checkpoints: Mapped[list["WorkflowApprovalCheckpointORM"]] = relationship(
        back_populates="target_artifact",
    )


class WorkflowEventORM(Base):
    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str | None] = mapped_column(String(32))
    step_status: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text(), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped["WorkflowRunORM"] = relationship(back_populates="events")
    step: Mapped["WorkflowStepORM | None"] = relationship(back_populates="events")


class WorkflowApprovalCheckpointORM(Base):
    __tablename__ = "workflow_approval_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    step_id: Mapped[int] = mapped_column(ForeignKey("workflow_steps.id", ondelete="CASCADE"))
    target_artifact_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resume_step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    resume_step_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    allowed_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    decision: Mapped[str | None] = mapped_column(String(32))
    decision_actor: Mapped[str | None] = mapped_column(String(255))
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision_feedback: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped["WorkflowRunORM"] = relationship(back_populates="approval_checkpoints")
    step: Mapped["WorkflowStepORM"] = relationship()
    target_artifact: Mapped["WorkflowArtifactORM"] = relationship(
        back_populates="approval_checkpoints",
    )


class WorkflowSpecialistInvocationORM(Base):
    __tablename__ = "workflow_specialist_invocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    step_id: Mapped[int] = mapped_column(ForeignKey("workflow_steps.id", ondelete="CASCADE"))
    specialist_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_artifact_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    output_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_artifacts.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[str | None] = mapped_column(Text())

    run: Mapped["WorkflowRunORM"] = relationship(back_populates="specialist_invocations")
    step: Mapped["WorkflowStepORM"] = relationship(back_populates="specialist_invocations")
    input_artifact: Mapped["WorkflowArtifactORM"] = relationship(
        back_populates="input_to_invocations",
        foreign_keys=[input_artifact_id],
    )
    output_artifact: Mapped["WorkflowArtifactORM | None"] = relationship(
        back_populates="output_from_invocations",
        foreign_keys=[output_artifact_id],
    )


class WorkflowSyncRecordORM(Base):
    __tablename__ = "workflow_sync_records"
    __table_args__ = (
        UniqueConstraint(
            "proposal_artifact_id",
            "proposal_version_number",
            "target_system",
            "sync_kind",
            "planned_item_key",
            "lineage_generation",
            name="uq_workflow_sync_record_identity",
        ),
        UniqueConstraint("idempotency_key", name="uq_workflow_sync_record_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    step_id: Mapped[int] = mapped_column(ForeignKey("workflow_steps.id", ondelete="CASCADE"))
    proposal_artifact_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proposal_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target_system: Mapped[str] = mapped_column(String(64), nullable=False)
    sync_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_item_key: Mapped[str] = mapped_column(String(255), nullable=False)
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(Text(), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    external_object_id: Mapped[str | None] = mapped_column(String(255))
    last_error_summary: Mapped[str | None] = mapped_column(Text())
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL")
    )
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lineage_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recovery_classification: Mapped[str | None] = mapped_column(String(64))
    recovery_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replay_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replay_requested_by: Mapped[str | None] = mapped_column(String(255))
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    termination_reason: Mapped[str | None] = mapped_column(Text())
    terminated_after_sync_count: Mapped[int | None] = mapped_column(Integer)
    terminated_after_planned_item_key: Mapped[str | None] = mapped_column(String(255))
    supersedes_sync_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_sync_records.id", ondelete="SET NULL")
    )
    replayed_from_sync_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_sync_records.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    run: Mapped["WorkflowRunORM"] = relationship(back_populates="sync_records")
    step: Mapped["WorkflowStepORM"] = relationship(
        back_populates="sync_records",
        foreign_keys=[step_id],
    )
    last_attempt_step: Mapped["WorkflowStepORM | None"] = relationship(
        foreign_keys=[last_attempt_step_id]
    )
    proposal_artifact: Mapped["WorkflowArtifactORM"] = relationship(
        foreign_keys=[proposal_artifact_id]
    )
    supersedes_sync_record: Mapped["WorkflowSyncRecordORM | None"] = relationship(
        remote_side="WorkflowSyncRecordORM.id",
        foreign_keys=[supersedes_sync_record_id],
    )
    replayed_from_sync_record: Mapped["WorkflowSyncRecordORM | None"] = relationship(
        remote_side="WorkflowSyncRecordORM.id",
        foreign_keys=[replayed_from_sync_record_id],
    )


class EmailMessageORM(Base):
    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    email_thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id", ondelete="CASCADE"))
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    internal_uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    email_draft_id: Mapped[int] = mapped_column(ForeignKey("email_drafts.id", ondelete="CASCADE"))
    email_thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id", ondelete="CASCADE"))
    action_proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("action_proposals.id", ondelete="SET NULL")
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_context: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    model_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    reasoning_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    refinement_metadata: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EmailSendAttemptORM(Base):
    __tablename__ = "email_send_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
    default_follow_up_business_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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


class ReplayQueueORM(Base):
    __tablename__ = "replay_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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
