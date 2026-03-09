import json

import pytest
from helm_llm.client import LLMClient
from helm_llm.contracts import EMAIL_TRIAGE_CONTRACT
from helm_llm.errors import LLMRequestError, LLMTimeoutError


class _FakeResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class _FakeResponsesAPI:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._error:
            raise self._error
        return self._result


class _FakeOpenAI:
    def __init__(self, responses) -> None:
        self.responses = responses


def test_run_contract_uses_responses_json_schema_and_store_false() -> None:
    result_payload = {
        "classification": "important",
        "priority": "high",
        "thread_summary": "Summary",
        "action_item": "Action",
        "should_create_digest_item": False,
    }
    fake_responses = _FakeResponsesAPI(result=_FakeResponse(json.dumps(result_payload)))
    client = LLMClient(openai_client=_FakeOpenAI(fake_responses), timeout_seconds=4)

    parsed = client.run_contract(EMAIL_TRIAGE_CONTRACT, {"message": "Hello"}, model="gpt-test")

    assert parsed["priority"] == "high"
    assert fake_responses.last_kwargs["store"] is False
    assert fake_responses.last_kwargs["model"] == "gpt-test"
    assert fake_responses.last_kwargs["text"]["format"]["type"] == "json_schema"
    assert fake_responses.last_kwargs["text"]["format"]["name"] == "email_triage_v1"


def test_run_contract_wraps_timeout_errors() -> None:
    fake_responses = _FakeResponsesAPI(error=TimeoutError("timed out"))
    client = LLMClient(openai_client=_FakeOpenAI(fake_responses))

    with pytest.raises(LLMTimeoutError):
        client.run_contract(EMAIL_TRIAGE_CONTRACT, {"message": "Hello"})


def test_run_contract_wraps_non_timeout_errors() -> None:
    fake_responses = _FakeResponsesAPI(error=RuntimeError("boom"))
    client = LLMClient(openai_client=_FakeOpenAI(fake_responses))

    with pytest.raises(LLMRequestError):
        client.run_contract(EMAIL_TRIAGE_CONTRACT, {"message": "Hello"})
