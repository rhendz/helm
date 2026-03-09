from helm_agents.study_agent import extract_study_artifacts


def test_extract_study_artifacts_detects_tasks_and_gaps() -> None:
    raw_text = """
    System design prep for distributed caches.
    Gap: I am confused about consistent hashing rebalancing.
    TODO: Practice two cache invalidation examples today.
    """

    artifacts = extract_study_artifacts(raw_text)

    assert artifacts["summary"]
    assert len(artifacts["knowledge_gaps"]) == 1
    assert artifacts["knowledge_gaps"][0]["severity"] == "medium"
    assert len(artifacts["learning_tasks"]) == 1
    assert artifacts["learning_tasks"][0]["priority"] == 1
