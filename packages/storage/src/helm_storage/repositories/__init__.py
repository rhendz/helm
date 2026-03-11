"""Storage repository implementations and contracts."""

from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.agent_runs import AgentRunStatus, SQLAlchemyAgentRunRepository
from helm_storage.repositories.classification_artifacts import (
    SQLAlchemyClassificationArtifactRepository,
)
from helm_storage.repositories.contracts import (
    ActionItemRepository,
    ActionProposalRepository,
    ClassificationArtifactRepository,
    DigestItemRepository,
    DraftReasoningArtifactRepository,
    DraftReplyRepository,
    EmailAgentConfigPatch,
    EmailAgentConfigRepository,
    EmailDraftRepository,
    EmailThreadRepository,
    NewActionItem,
    NewActionProposal,
    NewClassificationArtifact,
    NewDigestItem,
    NewDraftReasoningArtifact,
    NewDraftReply,
    NewEmailDraft,
    NewEmailThread,
    NewScheduledThreadTask,
    ScheduledThreadTaskRepository,
)
from helm_storage.repositories.digest_items import SQLAlchemyDigestItemRepository
from helm_storage.repositories.draft_reasoning_artifacts import (
    SQLAlchemyDraftReasoningArtifactRepository,
)
from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
from helm_storage.repositories.draft_transition_audits import (
    SQLAlchemyDraftTransitionAuditRepository,
)
from helm_storage.repositories.email_agent_config import SQLAlchemyEmailAgentConfigRepository
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_storage.repositories.job_controls import SQLAlchemyJobControlRepository
from helm_storage.repositories.opportunities import SQLAlchemyOpportunityRepository
from helm_storage.repositories.replay_queue import SQLAlchemyReplayQueueRepository
from helm_storage.repositories.scheduled_thread_tasks import SQLAlchemyScheduledThreadTaskRepository
from helm_storage.repositories.study_ingest import SQLAlchemyStudyIngestRepository

__all__ = [
    "ActionItemRepository",
    "ActionProposalRepository",
    "ClassificationArtifactRepository",
    "DigestItemRepository",
    "DraftReasoningArtifactRepository",
    "DraftReplyRepository",
    "EmailAgentConfigPatch",
    "EmailAgentConfigRepository",
    "EmailDraftRepository",
    "EmailThreadRepository",
    "NewActionItem",
    "NewActionProposal",
    "NewClassificationArtifact",
    "NewDigestItem",
    "NewDraftReasoningArtifact",
    "NewDraftReply",
    "NewEmailDraft",
    "NewEmailThread",
    "NewScheduledThreadTask",
    "ScheduledThreadTaskRepository",
    "SQLAlchemyActionProposalRepository",
    "SQLAlchemyActionItemRepository",
    "AgentRunStatus",
    "SQLAlchemyAgentRunRepository",
    "SQLAlchemyClassificationArtifactRepository",
    "SQLAlchemyDigestItemRepository",
    "SQLAlchemyDraftReasoningArtifactRepository",
    "SQLAlchemyDraftReplyRepository",
    "SQLAlchemyDraftTransitionAuditRepository",
    "SQLAlchemyEmailAgentConfigRepository",
    "SQLAlchemyEmailDraftRepository",
    "SQLAlchemyEmailMessageRepository",
    "SQLAlchemyEmailThreadRepository",
    "SQLAlchemyJobControlRepository",
    "SQLAlchemyOpportunityRepository",
    "SQLAlchemyReplayQueueRepository",
    "SQLAlchemyScheduledThreadTaskRepository",
    "SQLAlchemyStudyIngestRepository",
]
