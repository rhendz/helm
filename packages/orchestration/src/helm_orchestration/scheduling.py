from __future__ import annotations

from typing import Protocol

from helm_orchestration.schemas import ApprovalAction, ApprovalDecision, TaskSemantics


class ApprovalPolicy(Protocol):
    def evaluate(self, semantics: TaskSemantics) -> ApprovalDecision: ...


class ConditionalApprovalPolicy:
    """S01 stub: auto-approve high-confidence short tasks, ask otherwise.

    Full conflict/displacement logic lands in S02.
    """

    CONFIDENCE_THRESHOLD: float = 0.8
    MAX_AUTO_APPROVE_MINUTES: int = 120

    def evaluate(self, semantics: TaskSemantics) -> ApprovalDecision:
        if (
            semantics.confidence >= self.CONFIDENCE_THRESHOLD
            and semantics.sizing_minutes <= self.MAX_AUTO_APPROVE_MINUTES
        ):
            return ApprovalDecision(
                action=ApprovalAction.APPROVE,
                actor="system:conditional_policy",
                target_artifact_id=0,  # no artifact in S01 stub
            )
        return ApprovalDecision(
            action=ApprovalAction.REQUEST_REVISION,
            actor="system:conditional_policy",
            target_artifact_id=0,
            revision_feedback="Confidence or sizing outside auto-approve thresholds",
        )
