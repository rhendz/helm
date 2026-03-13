from helm_worker.jobs.registry import JOBS


def test_job_registry_contains_core_jobs() -> None:
    assert {"email_triage", "digest", "study", "scheduled_thread_tasks", "workflow_runs"}.issubset(
        JOBS.keys()
    )
