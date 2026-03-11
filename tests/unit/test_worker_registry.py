from helm_worker.jobs.registry import JOBS


def test_job_registry_contains_core_jobs() -> None:
    assert {
        "email_triage",
        "email_reconciliation_sweep",
        "digest",
        "scheduled_thread_tasks",
        "email_followup_scan",
        "email_send_recovery",
    }.issubset(JOBS.keys())
