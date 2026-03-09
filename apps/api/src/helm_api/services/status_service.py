from typing import Any

from helm_api.services.agent_run_service import list_recent_agent_runs


def _summarize_failures(items: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [run for run in items if run["status"] == "failed"]
    return {
        "failed_count": len(failures),
        "latest_failure": failures[0] if failures else None,
    }


def get_runtime_status() -> dict[str, Any]:
    runs_payload = list_recent_agent_runs(limit=10)
    run_items = runs_payload["items"]

    state = "bootstrapped"
    if runs_payload["storage"] != "ok" or any(run["status"] == "failed" for run in run_items):
        state = "degraded"

    return {
        "service": "api",
        "state": state,
        "runs": {
            "storage": runs_payload["storage"],
            "recent": run_items,
            **_summarize_failures(run_items),
        },
    }
