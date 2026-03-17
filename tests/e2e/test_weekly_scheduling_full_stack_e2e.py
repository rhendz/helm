"""Full-stack E2E test: weekly scheduling workflow → real Google Calendar events.

Covers the entire path that Telegram exercises, without Telegram or Docker:
  1. Create a workflow run in the real DB (same as /workflow_start)
  2. Run the worker in-process: task agent → calendar agent → await_schedule_approval
  3. Approve via submit_approval_decision (same path as /approve in Telegram)
  4. Run the worker again: apply_schedule → upsert 3 events via real Calendar API
  5. Assert all 3 events exist in Google Calendar with correct fingerprints
  6. Clean up created events

Skipped when GOOGLE_* credentials are not present (safe for CI).

Run manually:
  uv run --frozen --extra dev pytest tests/e2e/test_weekly_scheduling_full_stack_e2e.py -v -s
"""
from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from helm_api.services.workflow_status_service import (
    WorkflowStatusService,
    build_workflow_run_create_input,
)
from helm_connectors.google_calendar import GoogleCalendarAdapter, GoogleCalendarAuth
from helm_orchestration import ApprovalAction, ApprovalDecision
from helm_orchestration.schemas import SyncLookupRequest, SyncOperation, SyncTargetSystem
from helm_storage.db import SessionLocal
from helm_storage.repositories import (
    SQLAlchemyWorkflowSyncRecordRepository,
    WorkflowArtifactType,
    WorkflowRunStatus,
    WorkflowSyncStatus,
    WorkflowTargetSystem,
)

# ---------------------------------------------------------------------------
# Credential gate
# ---------------------------------------------------------------------------

_CREDS_PRESENT = all(
    os.getenv(v, "").strip()
    for v in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
)

pytestmark = pytest.mark.skipif(
    not _CREDS_PRESENT,
    reason="Google credentials not set (GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN)",
)

# ---------------------------------------------------------------------------
# Request text — same as a Telegram user would type
# ---------------------------------------------------------------------------

_WEEKLY_REQUEST = (
    "Schedule my week: "
    "Monday E2E test deep work 10am-12pm, "
    "Tuesday E2E test team sync 2pm-3pm, "
    "Wednesday E2E test focus block 9am-11am"
)
_ACTOR = "e2e-test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_worker_once(run_id: int) -> None:
    """Run one worker tick for a specific run_id in a fresh session."""
    from helm_worker.jobs.workflow_runs import _build_resume_service, _build_specialist_steps

    with SessionLocal() as session:
        resume_service = _build_resume_service(session, handlers=_build_specialist_steps())
        resume_service.resume_run(run_id)
        session.commit()


def _get_calendar_sync_records(run_id: int):
    with SessionLocal() as session:
        repo = SQLAlchemyWorkflowSyncRecordRepository(session)
        records = repo.list_for_run(run_id)
        # Detach from session by converting to plain dicts
        return [
            {
                "id": r.id,
                "target_system": r.target_system,
                "planned_item_key": r.planned_item_key,
                "status": r.status,
                "external_object_id": r.external_object_id,
                "payload_fingerprint": r.payload_fingerprint,
                "proposal_artifact_id": r.proposal_artifact_id,
                "proposal_version_number": r.proposal_version_number,
            }
            for r in records
            if r.target_system == WorkflowTargetSystem.CALENDAR_SYSTEM.value
        ]


# ---------------------------------------------------------------------------
# Test class — steps run in order, state shared via class attributes
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("cleanup_calendar_events")
class TestWeeklySchedulingFullStackE2E:
    """Full pipeline: create run → worker → approve → worker → verify Calendar."""

    run_id: int = 0
    created_event_ids: list[str] = []

    @pytest.fixture(scope="class", autouse=True)
    def cleanup_calendar_events(self) -> None:  # type: ignore[override]
        yield
        if self.created_event_ids:
            try:
                adapter = GoogleCalendarAdapter(GoogleCalendarAuth())
                service = adapter._get_service()
                for event_id in self.created_event_ids:
                    try:
                        service.events().delete(calendarId="primary", eventId=event_id).execute()
                    except Exception:
                        pass
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Step 1: create run
    # ------------------------------------------------------------------

    def test_01_create_run(self) -> None:
        """Create a weekly_scheduling run — equivalent to /workflow_start."""
        normalized = build_workflow_run_create_input(
            workflow_type="weekly_scheduling",
            first_step_name="dispatch_task_agent",
            request_text=_WEEKLY_REQUEST,
            submitted_by=_ACTOR,
            channel="e2e",
        )
        with SessionLocal() as session:
            svc = WorkflowStatusService(session)
            result = svc.create_run(normalized)
            session.commit()

        TestWeeklySchedulingFullStackE2E.run_id = result["id"]
        assert result["status"] == WorkflowRunStatus.PENDING.value, result["status"]
        assert result["current_step"] == "dispatch_task_agent"

    # ------------------------------------------------------------------
    # Step 2: worker tick — task agent + calendar agent
    # ------------------------------------------------------------------

    def test_02_worker_runs_agents(self) -> None:
        """Worker processes task agent then calendar agent, parks at await_schedule_approval."""
        _run_worker_once(self.run_id)  # dispatch_task_agent → dispatch_calendar_agent
        _run_worker_once(self.run_id)  # dispatch_calendar_agent → await_schedule_approval

        with SessionLocal() as session:
            svc = WorkflowStatusService(session)
            detail = svc.get_run_detail(self.run_id)

        assert detail is not None
        assert detail["status"] == "blocked", detail["status"]
        assert detail["current_step"] == "await_schedule_approval"
        assert detail["needs_action"] is True

        # Proposal must contain 3 time blocks
        proposal_versions = detail.get("proposal_versions") or []
        assert proposal_versions, "No proposal versions in detail"
        latest = proposal_versions[0]
        blocks = latest.get("time_blocks", [])
        assert len(blocks) == 3, f"Expected 3 time_blocks, got {len(blocks)}: {blocks}"

    # ------------------------------------------------------------------
    # Step 3: approve
    # ------------------------------------------------------------------

    def test_03_approve(self) -> None:
        """Approve the proposal — equivalent to /approve in Telegram."""
        with SessionLocal() as session:
            svc = WorkflowStatusService(session)
            detail = svc.get_run_detail(self.run_id)

        assert detail is not None
        checkpoint = detail.get("approval_checkpoint")
        assert checkpoint, f"No approval_checkpoint in detail"
        target_artifact_id = checkpoint["target_artifact_id"]
        assert target_artifact_id, "No target_artifact_id on checkpoint"

        with SessionLocal() as session:
            svc = WorkflowStatusService(session)
            result = svc.approve_run(
                self.run_id,
                actor=_ACTOR,
                target_artifact_id=target_artifact_id,
            )
            session.commit()

        assert result["status"] == WorkflowRunStatus.PENDING.value, (
            f"Expected pending after approval, got {result['status']}"
        )
        assert result["current_step"] == "apply_schedule", result["current_step"]
        assert result["needs_action"] is False

    # ------------------------------------------------------------------
    # Step 4: worker tick — apply_schedule writes to Calendar
    # ------------------------------------------------------------------

    def test_04_worker_applies_schedule(self) -> None:
        """Worker runs apply_schedule and writes 3 events to Google Calendar."""
        _run_worker_once(self.run_id)

        with SessionLocal() as session:
            svc = WorkflowStatusService(session)
            detail = svc.get_run_detail(self.run_id)

        assert detail is not None, f"Run {self.run_id} not found"
        assert detail["status"] == WorkflowRunStatus.COMPLETED.value, (
            f"Expected completed, got {detail['status']}. "
            f"Step: {detail.get('current_step')}. "
            f"Error: {detail.get('failure_summary')}"
        )

        calendar_records = _get_calendar_sync_records(self.run_id)
        assert len(calendar_records) == 3, (
            f"Expected 3 calendar sync records, got {len(calendar_records)}"
        )
        for rec in calendar_records:
            assert rec["status"] == WorkflowSyncStatus.SUCCEEDED.value, (
                f"{rec['planned_item_key']} has status {rec['status']}"
            )
            assert rec["external_object_id"], (
                f"{rec['planned_item_key']} has no external_object_id"
            )
            TestWeeklySchedulingFullStackE2E.created_event_ids.append(rec["external_object_id"])

    # ------------------------------------------------------------------
    # Step 5: events actually exist in Google Calendar
    # ------------------------------------------------------------------

    def test_05_events_exist_in_google_calendar(self) -> None:
        """Fetch each created event from the Calendar API and confirm it's live."""
        assert self.created_event_ids, "No event IDs — step 4 must have failed"

        adapter = GoogleCalendarAdapter(GoogleCalendarAuth())
        service = adapter._get_service()

        for event_id in self.created_event_ids:
            event = service.events().get(calendarId="primary", eventId=event_id).execute()
            assert event.get("status") != "cancelled", f"Event {event_id} is cancelled/deleted"
            assert event.get("summary"), f"Event {event_id} has no title"

    # ------------------------------------------------------------------
    # Step 6: reconcile — no false drift
    # ------------------------------------------------------------------

    def test_06_reconcile_no_drift(self) -> None:
        """Reconcile each calendar record against the live event — fingerprints must match."""
        calendar_records = _get_calendar_sync_records(self.run_id)
        assert len(calendar_records) == 3

        adapter = GoogleCalendarAdapter(GoogleCalendarAuth())
        for rec in calendar_records:
            lookup = SyncLookupRequest(
                proposal_artifact_id=rec["proposal_artifact_id"],
                proposal_version_number=rec["proposal_version_number"],
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key=rec["planned_item_key"],
                payload_fingerprint=rec["payload_fingerprint"],
                external_object_id=rec["external_object_id"],
            )
            result = adapter.reconcile_calendar_block(lookup)
            assert result.found is True, (
                f"Event not found for {rec['planned_item_key']} ({rec['external_object_id']})"
            )
            assert result.payload_fingerprint_matches is True, (
                f"False drift for {rec['planned_item_key']}: {result.details}"
            )
