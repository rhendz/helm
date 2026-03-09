from helm_orchestration.email_flow import (
    EmailTriageState,
    EmailTriageStep,
    build_email_triage_graph,
    run_email_triage_workflow,
)


def test_build_email_triage_graph_contains_spec_sequence() -> None:
    graph = build_email_triage_graph()

    assert graph[EmailTriageStep.MESSAGE_INGESTED] == EmailTriageStep.MESSAGE_STORED
    assert graph[EmailTriageStep.MESSAGE_STORED] == EmailTriageStep.EMAIL_CLASSIFIED
    assert graph[EmailTriageStep.EMAIL_CLASSIFIED] == EmailTriageStep.THREAD_SUMMARIZED
    assert graph[EmailTriageStep.THREAD_SUMMARIZED] == EmailTriageStep.ACTION_ITEM_UPSERTED
    assert graph[EmailTriageStep.ACTION_ITEM_UPSERTED] == EmailTriageStep.DRAFT_GENERATED
    assert graph[EmailTriageStep.DRAFT_GENERATED] == EmailTriageStep.DIGEST_ITEM_CREATED
    assert graph[EmailTriageStep.DIGEST_ITEM_CREATED] == EmailTriageStep.TELEGRAM_NOTIFIED
    assert graph[EmailTriageStep.TELEGRAM_NOTIFIED] == EmailTriageStep.AGENT_RUN_LOGGED
    assert graph[EmailTriageStep.AGENT_RUN_LOGGED] == EmailTriageStep.COMPLETED


def test_run_email_triage_workflow_emits_handoffs_for_storage_draft_digest() -> None:
    state = EmailTriageState(
        provider_message_id="msg-123",
        provider_thread_id="thread-123",
        should_generate_draft=True,
        should_create_digest_item=True,
        should_notify_telegram=True,
    )

    result = run_email_triage_workflow(state)

    assert result.step == EmailTriageStep.COMPLETED
    targets = [handoff.target for handoff in result.handoffs]
    assert "storage.persist_email_message" in targets
    assert "storage.upsert_action_item" in targets
    assert "agents.email.generate_draft" in targets
    assert "storage.create_draft_reply" in targets
    assert "storage.create_digest_item" in targets
    assert "apps.telegram.notify_high_priority" in targets
    assert "observability.log_agent_run" in targets
