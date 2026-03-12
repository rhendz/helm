from __future__ import annotations

from helm_orchestration import (
    CalendarSyncRequest,
    CalendarSyncResult,
    SyncLookupRequest,
    SyncLookupResult,
    SyncOutcomeStatus,
    SyncRetryDisposition,
)


class StubCalendarSystemAdapter:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, str]] = {}

    def upsert_calendar_block(self, request: CalendarSyncRequest) -> CalendarSyncResult:
        external_object_id = self._ensure_external_object_id(request.item.planned_item_key)
        self._records[request.item.planned_item_key] = {
            "external_object_id": external_object_id,
            "payload_fingerprint": request.item.payload_fingerprint,
        }
        return CalendarSyncResult(
            status=SyncOutcomeStatus.SUCCEEDED,
            retry_disposition=SyncRetryDisposition.TERMINAL,
            external_object_id=external_object_id,
        )

    def reconcile_calendar_block(self, request: SyncLookupRequest) -> SyncLookupResult:
        record = self._records.get(request.planned_item_key)
        if record is None:
            return SyncLookupResult(found=False, provider_state="missing")
        return SyncLookupResult(
            found=True,
            external_object_id=record["external_object_id"],
            payload_fingerprint_matches=record["payload_fingerprint"] == request.payload_fingerprint,
            provider_state="present",
        )

    @staticmethod
    def _ensure_external_object_id(planned_item_key: str) -> str:
        return planned_item_key.replace("calendar:", "calendar-")
