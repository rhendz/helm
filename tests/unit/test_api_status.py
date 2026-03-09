from helm_api.services.status_service import get_runtime_status


def test_status_shape() -> None:
    payload = get_runtime_status()
    assert payload["service"] == "api"
    assert "state" in payload
    assert "recent_failed_runs" in payload
