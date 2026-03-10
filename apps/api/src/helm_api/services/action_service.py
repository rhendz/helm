def list_actions() -> list[dict]:
    from email_agent.adapters import build_helm_runtime
    from email_agent.operator import list_open_actions

    return [
        {
            "id": item.id,
            "title": item.title,
            "priority": item.priority,
            "status": "open",
        }
        for item in list_open_actions(runtime=build_helm_runtime())
    ]
