def get_runtime_status() -> dict[str, str]:
    # TODO(v1-phase2): include DB ping, worker heartbeat, and connector statuses.
    return {"service": "api", "state": "bootstrapped"}
