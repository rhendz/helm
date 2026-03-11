def list_actions() -> list[dict]:
    from email_agent.operator import list_open_actions
    from helm_runtime.email_agent import build_email_agent_runtime

    return [
        {
            "id": item.id,
            "title": item.title,
            "priority": item.priority,
            "status": "open",
        }
        for item in list_open_actions(runtime=build_email_agent_runtime())
    ]
