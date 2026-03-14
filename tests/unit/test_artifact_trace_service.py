from helm_api.services.artifact_trace_service import get_artifact_trace


def test_get_artifact_trace_rejects_unsupported_artifact_type() -> None:
    payload = get_artifact_trace(artifact_type="unknown", artifact_id=7)
    assert payload["status"] == "not_found"
    assert payload["reason"] == "unsupported_artifact_type"
    assert payload["run_context"] == []
