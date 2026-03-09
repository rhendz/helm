import json

import pytest
from helm_llm.contracts import (
    DAILY_DIGEST_CONTRACT,
    EMAIL_TRIAGE_CONTRACT,
    STUDY_SUMMARY_CONTRACT,
)
from helm_llm.errors import LLMResponseFormatError


@pytest.mark.parametrize(
    ("contract", "expected_workflow"),
    [
        (EMAIL_TRIAGE_CONTRACT, "email_triage"),
        (DAILY_DIGEST_CONTRACT, "daily_digest"),
        (STUDY_SUMMARY_CONTRACT, "study_summary"),
    ],
)
def test_contract_metadata_shape(contract, expected_workflow: str) -> None:
    assert contract.workflow == expected_workflow
    assert contract.version == "v1"
    assert contract.contract_id == f"{expected_workflow}_v1"
    assert contract.output_schema["type"] == "object"


def test_contract_render_user_input_is_deterministic_json() -> None:
    payload = {"b": 1, "a": "x"}
    rendered = EMAIL_TRIAGE_CONTRACT.render_user_input(payload)
    assert rendered == '{"a": "x", "b": 1}'


def test_contract_parse_output_accepts_json_object() -> None:
    raw = json.dumps(
        {
            "classification": "important",
            "priority": "high",
            "thread_summary": "Budget and timeline request",
            "action_item": "Reply with next-call slots",
            "should_create_digest_item": True,
        }
    )
    parsed = EMAIL_TRIAGE_CONTRACT.parse_output(raw)
    assert parsed["classification"] == "important"
    assert parsed["should_create_digest_item"] is True


def test_contract_parse_output_rejects_non_json() -> None:
    with pytest.raises(LLMResponseFormatError):
        EMAIL_TRIAGE_CONTRACT.parse_output("not-json")


def test_contract_parse_output_rejects_non_object_root() -> None:
    with pytest.raises(LLMResponseFormatError):
        DAILY_DIGEST_CONTRACT.parse_output('["a", "b"]')
