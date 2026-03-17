"""Unit tests for TaskSemantics model, ConditionalApprovalPolicy, and LLMClient.infer_task_semantics."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from helm_orchestration import (
    ConditionalApprovalPolicy,
    TaskSemantics,
)
from helm_orchestration.schemas import ApprovalAction


# ---------------------------------------------------------------------------
# TaskSemantics model validation
# ---------------------------------------------------------------------------


def test_task_semantics_valid_construction() -> None:
    s = TaskSemantics(urgency="high", priority="medium", sizing_minutes=45, confidence=0.9)
    assert s.urgency == "high"
    assert s.priority == "medium"
    assert s.sizing_minutes == 45
    assert s.confidence == 0.9


def test_task_semantics_extra_fields_ignored() -> None:
    """extra='ignore' means unknown fields from LLM output don't raise."""
    s = TaskSemantics(
        urgency="low",
        priority="low",
        sizing_minutes=30,
        confidence=0.5,
        some_extra_llm_field="whatever",  # type: ignore[call-arg]
    )
    assert s.urgency == "low"
    assert not hasattr(s, "some_extra_llm_field")


def test_task_semantics_confidence_as_float() -> None:
    s = TaskSemantics(urgency="medium", priority="high", sizing_minutes=120, confidence=0.0)
    assert s.confidence == 0.0
    s2 = TaskSemantics(urgency="medium", priority="high", sizing_minutes=120, confidence=1.0)
    assert s2.confidence == 1.0


# ---------------------------------------------------------------------------
# ConditionalApprovalPolicy — table-driven edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "confidence,sizing_minutes,expected_action",
    [
        # Clear approve
        (0.9, 60, ApprovalAction.APPROVE),
        # Low confidence → revision
        (0.7, 60, ApprovalAction.REQUEST_REVISION),
        # Too long → revision
        (0.9, 180, ApprovalAction.REQUEST_REVISION),
        # Both bad → revision
        (0.5, 180, ApprovalAction.REQUEST_REVISION),
        # Exact thresholds → approve
        (0.8, 120, ApprovalAction.APPROVE),
        # Just below confidence → revision
        (0.79, 120, ApprovalAction.REQUEST_REVISION),
        # Just above sizing → revision
        (0.8, 121, ApprovalAction.REQUEST_REVISION),
    ],
)
def test_conditional_approval_policy(
    confidence: float, sizing_minutes: int, expected_action: ApprovalAction
) -> None:
    policy = ConditionalApprovalPolicy()
    semantics = TaskSemantics(
        urgency="medium",
        priority="medium",
        sizing_minutes=sizing_minutes,
        confidence=confidence,
    )
    decision = policy.evaluate(semantics)
    assert decision.action == expected_action
    assert decision.actor == "system:conditional_policy"
    assert decision.target_artifact_id == 0


def test_conditional_approval_policy_approve_has_no_revision_feedback() -> None:
    policy = ConditionalApprovalPolicy()
    semantics = TaskSemantics(urgency="high", priority="high", sizing_minutes=30, confidence=0.95)
    decision = policy.evaluate(semantics)
    assert decision.action == ApprovalAction.APPROVE
    assert decision.revision_feedback is None


def test_conditional_approval_policy_revision_has_feedback() -> None:
    policy = ConditionalApprovalPolicy()
    semantics = TaskSemantics(urgency="low", priority="low", sizing_minutes=200, confidence=0.5)
    decision = policy.evaluate(semantics)
    assert decision.action == ApprovalAction.REQUEST_REVISION
    assert decision.revision_feedback is not None
    assert len(decision.revision_feedback) > 0


# ---------------------------------------------------------------------------
# LLMClient.infer_task_semantics — mocked OpenAI client
# ---------------------------------------------------------------------------


def test_infer_task_semantics_returns_parsed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """infer_task_semantics should call responses.parse with correct args and return output_parsed."""
    from helm_llm.client import LLMClient

    expected = TaskSemantics(urgency="high", priority="high", sizing_minutes=60, confidence=0.9)

    fake_response = MagicMock()
    fake_response.output_parsed = expected

    fake_responses = MagicMock()
    fake_responses.parse.return_value = fake_response

    fake_openai = MagicMock()
    fake_openai.responses = fake_responses

    # Bypass __init__ to avoid needing OPENAI_API_KEY
    client = object.__new__(LLMClient)
    client._client = fake_openai  # type: ignore[attr-defined]

    result = client.infer_task_semantics("book flights this week")

    assert result is expected
    fake_responses.parse.assert_called_once()
    call_kwargs = fake_responses.parse.call_args.kwargs
    assert call_kwargs["input"] == "book flights this week"
    assert call_kwargs["text_format"] is TaskSemantics
    assert "instructions" in call_kwargs
    assert isinstance(call_kwargs["instructions"], str)
    assert len(call_kwargs["instructions"]) > 20


def test_infer_task_semantics_uses_custom_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """When model= is passed explicitly it should be forwarded to responses.parse."""
    from helm_llm.client import LLMClient

    expected = TaskSemantics(urgency="low", priority="low", sizing_minutes=30, confidence=0.6)

    fake_response = MagicMock()
    fake_response.output_parsed = expected

    fake_responses = MagicMock()
    fake_responses.parse.return_value = fake_response

    fake_openai = MagicMock()
    fake_openai.responses = fake_responses

    client = object.__new__(LLMClient)
    client._client = fake_openai  # type: ignore[attr-defined]

    client.infer_task_semantics("quick errand", model="gpt-4o")

    call_kwargs = fake_responses.parse.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o"


def test_infer_task_semantics_falls_back_to_env_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """When model= is None, it should use OPENAI_MODEL env var or default."""
    import os

    from helm_llm.client import LLMClient

    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-nano")

    expected = TaskSemantics(urgency="low", priority="low", sizing_minutes=15, confidence=0.7)

    fake_response = MagicMock()
    fake_response.output_parsed = expected

    fake_responses = MagicMock()
    fake_responses.parse.return_value = fake_response

    fake_openai = MagicMock()
    fake_openai.responses = fake_responses

    client = object.__new__(LLMClient)
    client._client = fake_openai  # type: ignore[attr-defined]

    client.infer_task_semantics("schedule a meeting")

    call_kwargs = fake_responses.parse.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4.1-nano"
