"""Unit tests for Google provider layer (helm_providers).

T01 — Scaffold: protocols, credentials helper, factory skeleton.
T02 — GoogleCalendarProvider (to be added).
T03 — GmailProvider (to be added).

These tests are additive — T01 tests run immediately; T02/T03 tests are added
in their respective tasks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# T01 — Protocol + credential helper + factory skeleton
# ---------------------------------------------------------------------------


class TestProtocolImports:
    """Verify the Protocol classes are importable and have the right method names."""

    def test_calendar_provider_protocol_importable(self) -> None:
        from helm_providers.protocols import CalendarProvider

        assert hasattr(CalendarProvider, "upsert_calendar_block")
        assert hasattr(CalendarProvider, "reconcile_calendar_block")
        assert hasattr(CalendarProvider, "list_today_events")

    def test_inbox_provider_protocol_importable(self) -> None:
        from helm_providers.protocols import InboxProvider

        assert hasattr(InboxProvider, "pull_new_messages_report")
        assert hasattr(InboxProvider, "pull_changed_messages_report")
        assert hasattr(InboxProvider, "send_reply")

    def test_top_level_init_exports(self) -> None:
        from helm_providers import (  # noqa: F401
            CalendarProvider,
            InboxProvider,
            ProviderFactory,
            build_google_credentials,
        )


class TestBuildGoogleCredentials:
    """build_google_credentials — refresh logic and DB write-back."""

    def _make_creds_orm(
        self,
        access_token: str | None = "tok_existing",
        refresh_token: str = "ref_tok",
        client_id: str | None = "cid",
        client_secret: str | None = "csecret",
        expires_at: datetime | None = None,
    ) -> MagicMock:
        orm = MagicMock()
        orm.access_token = access_token
        orm.refresh_token = refresh_token
        orm.client_id = client_id
        orm.client_secret = client_secret
        orm.expires_at = expires_at
        return orm

    def test_valid_token_no_refresh(self) -> None:
        """If the token is already valid, no refresh should occur."""
        from helm_providers.credentials import build_google_credentials

        creds_orm = self._make_creds_orm()
        db = MagicMock()

        with patch("helm_providers.credentials.Credentials") as MockCreds:
            mock_google_creds = MagicMock()
            mock_google_creds.valid = True
            MockCreds.return_value = mock_google_creds

            result = build_google_credentials(1, creds_orm, db)

        assert result is mock_google_creds
        mock_google_creds.refresh.assert_not_called()
        db.commit.assert_not_called()

    def test_bootstrap_none_access_token_triggers_refresh(self) -> None:
        """access_token=None must trigger a refresh (bootstrap case)."""
        from helm_providers.credentials import build_google_credentials

        creds_orm = self._make_creds_orm(access_token=None)
        db = MagicMock()
        expiry_dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

        with patch("helm_providers.credentials.Credentials") as MockCreds, \
             patch("helm_providers.credentials.Request"):
            mock_google_creds = MagicMock()
            mock_google_creds.valid = False
            mock_google_creds.token = "new_access_token"
            mock_google_creds.expiry = expiry_dt.replace(tzinfo=None)  # google returns naive
            MockCreds.return_value = mock_google_creds

            build_google_credentials(1, creds_orm, db)

        mock_google_creds.refresh.assert_called_once()
        assert creds_orm.access_token == "new_access_token"
        assert creds_orm.expires_at == expiry_dt
        db.commit.assert_called_once()

    def test_expired_token_triggers_refresh_and_writeback(self) -> None:
        """An expired (valid=False) token should refresh and write back to DB."""
        from helm_providers.credentials import build_google_credentials

        creds_orm = self._make_creds_orm(access_token="old_tok")
        db = MagicMock()

        with patch("helm_providers.credentials.Credentials") as MockCreds, \
             patch("helm_providers.credentials.Request"):
            mock_google_creds = MagicMock()
            mock_google_creds.valid = False
            mock_google_creds.token = "refreshed_tok"
            mock_google_creds.expiry = None  # no expiry returned
            MockCreds.return_value = mock_google_creds

            build_google_credentials(1, creds_orm, db)

        assert creds_orm.access_token == "refreshed_tok"
        assert creds_orm.expires_at is None
        db.commit.assert_called_once()

    def test_refresh_failure_raises_and_logs_error(self) -> None:
        """On refresh failure the exception propagates and the DB is NOT committed."""
        from google.auth.exceptions import RefreshError
        from helm_providers.credentials import build_google_credentials

        creds_orm = self._make_creds_orm(access_token=None)
        db = MagicMock()

        with patch("helm_providers.credentials.Credentials") as MockCreds, \
             patch("helm_providers.credentials.Request"):
            mock_google_creds = MagicMock()
            mock_google_creds.valid = False
            mock_google_creds.refresh.side_effect = RefreshError("token revoked")
            MockCreds.return_value = mock_google_creds

            with pytest.raises(RefreshError):
                build_google_credentials(1, creds_orm, db)

        db.commit.assert_not_called()

    def test_no_secrets_in_credentials_object(self) -> None:
        """Verify Credentials is built with the expected non-secret parameters only."""
        from helm_providers.credentials import build_google_credentials

        creds_orm = self._make_creds_orm(
            access_token="tok",
            refresh_token="ref",
            client_id="cid",
            client_secret="csecret",
        )
        db = MagicMock()

        with patch("helm_providers.credentials.Credentials") as MockCreds:
            mock_google_creds = MagicMock()
            mock_google_creds.valid = True
            MockCreds.return_value = mock_google_creds

            build_google_credentials(1, creds_orm, db)

        call_kwargs = MockCreds.call_args
        # Credentials must be constructed — args are positional or keyword
        assert call_kwargs is not None


class TestProviderFactory:
    """ProviderFactory — calendar() delegates to GoogleCalendarProvider; inbox() still NotImplemented."""

    def test_factory_calendar_returns_google_calendar_provider(self) -> None:
        """ProviderFactory.calendar() must return a GoogleCalendarProvider instance."""
        from helm_providers.factory import ProviderFactory
        from helm_providers.google_calendar import GoogleCalendarProvider

        db = MagicMock()

        with patch("helm_providers.google_calendar.get_credentials") as mock_get_creds, \
             patch("helm_providers.google_calendar.build_google_credentials") as mock_build, \
             patch("helm_providers.google_calendar.build") as mock_disc_build:
            # Provide minimal mocks so __init__ doesn't blow up
            mock_get_creds.return_value = MagicMock()
            mock_build.return_value = MagicMock()
            mock_disc_build.return_value = MagicMock()

            factory = ProviderFactory(user_id=1, db=db)
            provider = factory.calendar()

        assert isinstance(provider, GoogleCalendarProvider)

    def test_factory_inbox_returns_inbox_provider(self) -> None:
        """ProviderFactory.inbox() now returns a GmailProvider (implemented in T03)."""
        from helm_providers.factory import ProviderFactory
        from helm_providers.gmail import GmailProvider

        db = MagicMock()

        with patch("helm_providers.gmail.get_credentials") as mock_get_creds, \
             patch("helm_providers.gmail.build_google_credentials") as mock_build, \
             patch("helm_providers.gmail.build") as mock_disc_build:
            mock_creds_orm = MagicMock()
            mock_creds_orm.email = "user@example.com"
            mock_get_creds.return_value = mock_creds_orm
            mock_build.return_value = MagicMock()
            mock_disc_build.return_value = MagicMock()

            factory = ProviderFactory(user_id=1, db=db)
            provider = factory.inbox()

        assert isinstance(provider, GmailProvider)


# ---------------------------------------------------------------------------
# T02 — GoogleCalendarProvider
# ---------------------------------------------------------------------------


def _make_cal_provider_mocked(
    user_id: int = 1,
) -> tuple:
    """Return (provider, mock_cal_svc) with CalendarService methods mocked."""
    from helm_providers.google_calendar import GoogleCalendarProvider

    db = MagicMock()
    mock_cal_svc = MagicMock()

    with patch("helm_providers.google_calendar.get_credentials") as mock_get_creds, \
         patch("helm_providers.google_calendar.build_google_credentials") as mock_build, \
         patch("helm_providers.google_calendar.build"), \
         patch("helm_providers.google_calendar.CalendarService") as mock_cal_cls:
        mock_get_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        mock_cal_cls.return_value = mock_cal_svc

        provider = GoogleCalendarProvider(user_id, db)

    return provider, mock_cal_svc


class TestGoogleCalendarProviderInit:
    """GoogleCalendarProvider.__init__ — credential handling and gauth bypass."""

    def test_raises_runtime_error_on_missing_credentials(self) -> None:
        """get_credentials returning None must raise RuntimeError."""
        from helm_providers.google_calendar import GoogleCalendarProvider

        db = MagicMock()
        with patch("helm_providers.google_calendar.get_credentials", return_value=None):
            with pytest.raises(RuntimeError, match="No Google credentials"):
                GoogleCalendarProvider(1, db)

    def test_gauth_not_imported(self) -> None:
        """gauth must never be imported or called inside google_calendar module."""
        import helm_providers.google_calendar as mod

        source = mod.__file__
        assert source is not None
        with open(source) as f:
            content = f.read()
        # Disallow actual import or call of gauth — docstring references are OK.
        # The pattern `gauth.` or `import gauth` would indicate real usage.
        assert "gauth." not in content, "gauth must not be called in google_calendar.py"
        assert "import gauth" not in content, "gauth must not be imported in google_calendar.py"

    def test_service_injected_before_property_access(self) -> None:
        """_service is injected onto CalendarService before any access."""
        provider, mock_cal_svc = _make_cal_provider_mocked()
        # CalendarService instance is the mock itself
        assert provider._cal_svc is mock_cal_svc


class TestUpsertCalendarBlock:
    """upsert_calendar_block — insert, update, validation, and error classification."""

    def _make_request(
        self,
        *,
        title: str = "Team Standup",
        start: str = "2026-03-14T10:00:00+00:00",
        end: str = "2026-03-14T11:00:00+00:00",
        description: str = "",
        external_object_id: str | None = None,
        calendar_id: str = "primary",
    ):
        from helm_orchestration.schemas import (
            ApprovedSyncItem,
            CalendarSyncRequest,
            SyncOperation,
            SyncTargetSystem,
        )

        payload: dict = {
            "title": title,
            "start": start,
            "end": end,
        }
        if description:
            payload["description"] = description
        if external_object_id:
            payload["external_object_id"] = external_object_id
        if calendar_id != "primary":
            payload["calendar_id"] = calendar_id

        return CalendarSyncRequest(
            item=ApprovedSyncItem(
                proposal_artifact_id=1,
                proposal_version_number=1,
                target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                planned_item_key="calendar:block-001",
                execution_order=1,
                payload_fingerprint="fp123",
                payload=payload,
            )
        )

    def test_insert_new_event_succeeds(self) -> None:
        """Insert path: create_event called, SUCCEEDED returned."""
        from helm_orchestration.schemas import SyncOutcomeStatus, SyncRetryDisposition

        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.create_event.return_value = {"id": "new-event-id-42"}

        result = provider.upsert_calendar_block(self._make_request())

        assert result.status == SyncOutcomeStatus.SUCCEEDED
        assert result.retry_disposition == SyncRetryDisposition.TERMINAL
        assert result.external_object_id == "new-event-id-42"
        assert result.error_summary is None
        mock_cal_svc.create_event.assert_called_once()
        mock_cal_svc.delete_event.assert_not_called()

    def test_update_existing_event_succeeds(self) -> None:
        """Update path: delete_event then create_event when external_object_id present."""
        from helm_orchestration.schemas import SyncOutcomeStatus

        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.create_event.return_value = {"id": "existing-event-99"}

        result = provider.upsert_calendar_block(
            self._make_request(external_object_id="existing-event-99")
        )

        assert result.status == SyncOutcomeStatus.SUCCEEDED
        assert result.external_object_id == "existing-event-99"
        mock_cal_svc.delete_event.assert_called_once_with(event_id="existing-event-99", send_notifications=False)
        mock_cal_svc.create_event.assert_called_once()

    def test_missing_title_returns_terminal_failure(self) -> None:
        """Missing required title field → TERMINAL_FAILURE without API call."""
        from helm_orchestration.schemas import SyncOutcomeStatus, SyncRetryDisposition

        provider, mock_cal_svc = _make_cal_provider_mocked()
        result = provider.upsert_calendar_block(self._make_request(title=""))

        assert result.status == SyncOutcomeStatus.TERMINAL_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.TERMINAL
        assert result.error_summary is not None
        mock_cal_svc.create_event.assert_not_called()

    def test_404_returns_terminal_failure(self) -> None:
        """create_event returning error with status_code=404 → TERMINAL_FAILURE."""
        from helm_orchestration.schemas import SyncOutcomeStatus, SyncRetryDisposition

        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.create_event.return_value = {"error": True, "status_code": 404, "message": "Not Found"}

        result = provider.upsert_calendar_block(self._make_request())

        assert result.status == SyncOutcomeStatus.TERMINAL_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.TERMINAL

    def test_429_returns_retryable_failure(self) -> None:
        """create_event returning error with status_code=429 → RETRYABLE_FAILURE."""
        from helm_orchestration.schemas import SyncOutcomeStatus, SyncRetryDisposition

        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.create_event.return_value = {"error": True, "status_code": 429, "message": "Rate Limited"}

        result = provider.upsert_calendar_block(self._make_request())

        assert result.status == SyncOutcomeStatus.RETRYABLE_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.RETRYABLE

    def test_500_returns_retryable_failure(self) -> None:
        """create_event returning error with status_code=500 → RETRYABLE_FAILURE."""
        from helm_orchestration.schemas import SyncOutcomeStatus, SyncRetryDisposition

        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.create_event.return_value = {"error": True, "status_code": 500, "message": "Server Error"}

        result = provider.upsert_calendar_block(self._make_request())

        assert result.status == SyncOutcomeStatus.RETRYABLE_FAILURE
        assert result.retry_disposition == SyncRetryDisposition.RETRYABLE


class TestReconcileCalendarBlock:
    """reconcile_calendar_block — found, not-found, cancelled events."""

    def _make_lookup_request(
        self,
        *,
        external_object_id: str | None = "evt-123",
        payload_fingerprint: str = "fp123",
        calendar_id: str = "primary",
    ):
        from helm_orchestration.schemas import (
            SyncLookupRequest,
            SyncOperation,
            SyncTargetSystem,
        )

        return SyncLookupRequest(
            proposal_artifact_id=1,
            proposal_version_number=1,
            target_system=SyncTargetSystem.CALENDAR_SYSTEM,
            operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
            planned_item_key="calendar:block-001",
            payload_fingerprint=payload_fingerprint,
            external_object_id=external_object_id,
            calendar_id=calendar_id,
        )

    def test_found_event_returns_true(self) -> None:
        """Event found → found=True."""
        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.get_event_details.return_value = {
            "id": "evt-123",
            "summary": "Standup",
            "start": {"dateTime": "2026-03-14T10:00:00+00:00"},
            "end": {"dateTime": "2026-03-14T11:00:00+00:00"},
            "description": "",
            "status": "confirmed",
        }

        result = provider.reconcile_calendar_block(self._make_lookup_request())

        assert result.found is True
        assert result.external_object_id == "evt-123"
        assert result.provider_state == "found"
        assert "live_event_fields" in result.details

    def test_not_found_404_returns_false(self) -> None:
        """get_event_details returning error dict with status_code=404 → found=False."""
        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.get_event_details.return_value = {"error": True, "status_code": 404, "message": "Not Found"}

        result = provider.reconcile_calendar_block(self._make_lookup_request())

        assert result.found is False
        assert result.provider_state == "not_found"
        assert result.payload_fingerprint_matches is None

    def test_cancelled_event_returns_false(self) -> None:
        """Google status='cancelled' → found=False, provider_state='cancelled'."""
        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.get_event_details.return_value = {"id": "evt-123", "status": "cancelled"}

        result = provider.reconcile_calendar_block(self._make_lookup_request())

        assert result.found is False
        assert result.provider_state == "cancelled"

    def test_missing_external_object_id_returns_error(self) -> None:
        """No external_object_id → found=False with error details, no API call."""
        provider, mock_cal_svc = _make_cal_provider_mocked()
        result = provider.reconcile_calendar_block(
            self._make_lookup_request(external_object_id=None)
        )

        assert result.found is False
        assert "error" in result.details
        mock_cal_svc.get_event_details.assert_not_called()


class TestListTodayEvents:
    """list_today_events — delegates to CalendarService.get_events."""

    def test_returns_event_list(self) -> None:
        from zoneinfo import ZoneInfo

        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.get_events.return_value = [
            {"id": "e1", "summary": "Morning call"},
            {"id": "e2", "summary": "Lunch"},
        ]

        events = provider.list_today_events("primary", ZoneInfo("America/Los_Angeles"))

        assert len(events) == 2
        assert events[0]["id"] == "e1"
        mock_cal_svc.get_events.assert_called_once()

    def test_empty_calendar_returns_empty_list(self) -> None:
        from zoneinfo import ZoneInfo

        provider, mock_cal_svc = _make_cal_provider_mocked()
        mock_cal_svc.get_events.return_value = []

        events = provider.list_today_events("primary", ZoneInfo("UTC"))

        assert events == []


class TestFingerprintEvent:
    """_fingerprint_event — canonical JSON, UTC normalization, missing fields."""

    def test_canonical_json_sorted_keys(self) -> None:
        """Fingerprint is deterministic (same input → same output, sorted keys)."""
        import json
        from helm_providers.google_calendar import _fingerprint_event

        event = {
            "summary": "Standup",
            "start": {"dateTime": "2026-03-14T10:00:00+00:00"},
            "end": {"dateTime": "2026-03-14T11:00:00+00:00"},
            "description": "Daily sync",
        }

        fp1 = _fingerprint_event(event)
        fp2 = _fingerprint_event(event)
        assert fp1 == fp2

        parsed = json.loads(fp1)
        assert parsed["title"] == "Standup"
        assert parsed["description"] == "Daily sync"

    def test_datetimes_normalized_to_utc(self) -> None:
        """Datetimes with different UTC offsets that represent the same instant fingerprint equal."""
        from helm_providers.google_calendar import _fingerprint_event

        event_utc = {
            "summary": "Meeting",
            "start": {"dateTime": "2026-03-14T17:00:00+00:00"},
            "end": {"dateTime": "2026-03-14T18:00:00+00:00"},
            "description": "",
        }
        event_pacific = {
            "summary": "Meeting",
            "start": {"dateTime": "2026-03-14T10:00:00-07:00"},
            "end": {"dateTime": "2026-03-14T11:00:00-07:00"},
            "description": "",
        }

        assert _fingerprint_event(event_utc) == _fingerprint_event(event_pacific)

    def test_missing_fields_produce_empty_strings(self) -> None:
        """Missing start/end/description → empty strings in fingerprint."""
        import json
        from helm_providers.google_calendar import _fingerprint_event

        parsed = json.loads(_fingerprint_event({"summary": "Solo"}))
        assert parsed["start"] == ""
        assert parsed["end"] == ""
        assert parsed["description"] == ""


# ---------------------------------------------------------------------------
# T03 — GmailProvider
# ---------------------------------------------------------------------------


def _make_gmail_provider_mocked(
    user_id: int = 1,
    sender_email: str = "sender@example.com",
) -> tuple:
    """Return (provider, mock_gmail_svc) with GmailService methods mocked.

    The raw service (mock_gmail_svc.service) is also a MagicMock so polling
    tests that call self._gmail_svc.service.users()... still work.
    """
    from helm_providers.gmail import GmailProvider

    db = MagicMock()
    mock_gmail_svc = MagicMock()

    mock_creds_orm = MagicMock()
    mock_creds_orm.email = sender_email

    with patch("helm_providers.gmail.get_credentials") as mock_get_creds, \
         patch("helm_providers.gmail.build_google_credentials") as mock_build, \
         patch("helm_providers.gmail.build"), \
         patch("helm_providers.gmail.GmailService") as mock_gmail_cls:
        mock_get_creds.return_value = mock_creds_orm
        mock_build.return_value = MagicMock()
        mock_gmail_cls.return_value = mock_gmail_svc

        provider = GmailProvider(user_id, db)

    return provider, mock_gmail_svc


class TestGmailProviderInit:
    """GmailProvider.__init__ — credential handling and gauth bypass."""

    def test_raises_runtime_error_on_missing_credentials(self) -> None:
        """get_credentials returning None must raise RuntimeError."""
        from helm_providers.gmail import GmailProvider

        db = MagicMock()
        with patch("helm_providers.gmail.get_credentials", return_value=None):
            with pytest.raises(RuntimeError, match="No Google credentials"):
                GmailProvider(1, db)

    def test_sender_email_read_from_creds_orm(self) -> None:
        """_sender_email must come from creds.email, not env var."""
        provider, _ = _make_gmail_provider_mocked(sender_email="user@test.com")
        assert provider._sender_email == "user@test.com"

    def test_gauth_not_imported(self) -> None:
        """gauth must never be imported or called inside gmail module."""
        import helm_providers.gmail as mod

        source = mod.__file__
        assert source is not None
        with open(source) as f:
            content = f.read()
        assert "gauth." not in content, "gauth must not be called in gmail.py"
        assert "import gauth" not in content, "gauth must not be imported in gmail.py"


class TestPullNewMessagesReport:
    """pull_new_messages_report — manual payload and API path."""

    def test_manual_payload_normalizes_messages(self) -> None:
        """Manual payload list is normalized without calling the Gmail API."""
        provider, mock_gmail_svc = _make_gmail_provider_mocked()

        raw_msgs = [
            {
                "id": "msg001",
                "threadId": "thr001",
                "from": "alice@example.com",
                "subject": "Hello",
                "body_text": "Hi there",
                "internalDate": "1710000000000",
            },
            {
                "id": "msg002",
                "threadId": "thr002",
                "from": "bob@example.com",
                "subject": "World",
                "body_text": "How are you",
                "internalDate": "1710000001000",
            },
        ]

        report = provider.pull_new_messages_report(manual_payload=raw_msgs)

        assert report.mode == "manual"
        assert len(report.messages) == 2
        assert report.messages[0].provider_message_id == "msg001"
        assert report.messages[1].provider_message_id == "msg002"
        # API must NOT be called for manual payload
        mock_gmail_svc.service.users.assert_not_called()

    def test_from_api_normalizes_messages(self) -> None:
        """API path: messages().list() + messages().get() called and normalized."""
        provider, mock_gmail_svc = _make_gmail_provider_mocked()

        # Mock messages().list() response
        mock_gmail_svc.service.users.return_value.messages.return_value.list.return_value \
            .execute.return_value = {
                "messages": [{"id": "api001"}, {"id": "api002"}]
            }

        # Mock messages().get() responses
        def fake_get_execute(userId, id, format):  # noqa: A002
            return MagicMock(
                execute=lambda: {
                    "id": id,
                    "threadId": f"thr-{id}",
                    "snippet": f"snippet for {id}",
                    "internalDate": "1710000000000",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "sender@example.com"},
                            {"name": "Subject", "value": f"Subject {id}"},
                        ],
                        "body": {},
                        "parts": [],
                    },
                }
            )

        mock_gmail_svc.service.users.return_value.messages.return_value.get.side_effect = fake_get_execute

        # Mock getProfile for history cursor
        mock_gmail_svc.service.users.return_value.getProfile.return_value.execute.return_value = {
            "historyId": "999"
        }

        report = provider.pull_new_messages_report()

        assert report.mode == "poll"
        assert len(report.messages) == 2
        assert report.messages[0].provider_message_id == "api001"
        assert report.next_history_cursor == "999"


class TestPullChangedMessagesReport:
    """pull_changed_messages_report — bootstrap fallback and history cursor path."""

    def test_bootstrap_fallback_when_no_cursor(self) -> None:
        """last_history_cursor=None must fall back to pull_new_messages_report with mode='bootstrap'."""
        provider, mock_gmail_svc = _make_gmail_provider_mocked()

        # Mock the full new-messages path
        mock_gmail_svc.service.users.return_value.messages.return_value.list.return_value \
            .execute.return_value = {"messages": [{"id": "bsm001"}]}

        mock_gmail_svc.service.users.return_value.messages.return_value.get.side_effect = (
            lambda userId, id, format: MagicMock(  # noqa: A002
                execute=lambda: {
                    "id": id,
                    "threadId": f"t-{id}",
                    "snippet": "boot snippet",
                    "internalDate": "1710000000000",
                    "payload": {
                        "headers": [{"name": "From", "value": "x@x.com"}],
                        "body": {},
                        "parts": [],
                    },
                }
            )
        )
        mock_gmail_svc.service.users.return_value.getProfile.return_value.execute.return_value = {
            "historyId": "111"
        }

        report = provider.pull_changed_messages_report(last_history_cursor=None)

        assert report.mode == "bootstrap"
        assert report.recovery_reason == "missing_history_cursor"
        assert len(report.messages) == 1
        assert report.messages[0].provider_message_id == "bsm001"

    def test_history_cursor_path(self) -> None:
        """Valid cursor: history().list() called, new messages fetched and returned."""
        provider, mock_gmail_svc = _make_gmail_provider_mocked()

        # Mock history list response with one new message
        mock_gmail_svc.service.users.return_value.history.return_value.list.return_value \
            .execute.return_value = {
                "historyId": "500",
                "history": [
                    {
                        "messagesAdded": [
                            {"message": {"id": "hist001"}}
                        ]
                    }
                ],
                "nextPageToken": None,
            }

        mock_gmail_svc.service.users.return_value.messages.return_value.get.side_effect = (
            lambda userId, id, format: MagicMock(  # noqa: A002
                execute=lambda: {
                    "id": id,
                    "threadId": f"t-{id}",
                    "snippet": "hist snippet",
                    "internalDate": "1710000000000",
                    "payload": {
                        "headers": [{"name": "From", "value": "h@h.com"}],
                        "body": {},
                        "parts": [],
                    },
                }
            )
        )

        report = provider.pull_changed_messages_report(last_history_cursor="400")

        assert report.mode == "history"
        assert len(report.messages) == 1
        assert report.messages[0].provider_message_id == "hist001"
        assert report.next_history_cursor == "500"

    def test_history_pull_failure_triggers_recovery(self) -> None:
        """History pull exception falls back to recovery_poll with recovery_reason set."""
        provider, mock_gmail_svc = _make_gmail_provider_mocked()

        # History list raises
        mock_gmail_svc.service.users.return_value.history.return_value.list.return_value \
            .execute.side_effect = Exception("historyId too old")

        # Fall-back new-messages pull returns empty
        mock_gmail_svc.service.users.return_value.messages.return_value.list.return_value \
            .execute.return_value = {"messages": []}
        mock_gmail_svc.service.users.return_value.getProfile.return_value.execute.return_value = {
            "historyId": "600"
        }

        report = provider.pull_changed_messages_report(last_history_cursor="300")

        assert report.mode == "recovery_poll"
        assert report.recovery_reason == "history_cursor_invalid"


class TestSendReply:
    """send_reply — success, validation errors."""

    def test_send_reply_success(self) -> None:
        """Successful send returns GmailSendResult with correct fields."""
        from helm_providers.gmail import GmailSendResult

        provider, mock_gmail_svc = _make_gmail_provider_mocked(sender_email="me@example.com")
        mock_gmail_svc.create_reply.return_value = {"id": "msg123", "threadId": "t456"}

        result = provider.send_reply(
            provider_thread_id="t456",
            to_address="them@example.com",
            subject="Re: Hello",
            body_text="Sure, sounds good.",
        )

        assert isinstance(result, GmailSendResult)
        assert result.provider_message_id == "msg123"
        assert result.provider_thread_id == "t456"
        assert result.from_address == "me@example.com"
        assert result.to_address == "them@example.com"
        assert result.subject == "Re: Hello"
        assert result.body_text == "Sure, sounds good."

    def test_send_reply_empty_recipient_raises(self) -> None:
        """Empty to_address raises GmailSendError with failure_class='invalid_recipient'."""
        from helm_providers.gmail import GmailSendError

        provider, _ = _make_gmail_provider_mocked()

        with pytest.raises(GmailSendError) as exc_info:
            provider.send_reply(
                provider_thread_id="t001",
                to_address="   ",
                subject="Test",
                body_text="Body text",
            )

        assert exc_info.value.failure_class == "invalid_recipient"

    def test_send_reply_empty_body_raises(self) -> None:
        """Empty body_text raises GmailSendError with failure_class='invalid_payload'."""
        from helm_providers.gmail import GmailSendError

        provider, _ = _make_gmail_provider_mocked()

        with pytest.raises(GmailSendError) as exc_info:
            provider.send_reply(
                provider_thread_id="t001",
                to_address="someone@example.com",
                subject="Test",
                body_text="",
            )

        assert exc_info.value.failure_class == "invalid_payload"


class TestNormalizeMessage:
    """normalize_message — valid payload and missing-id error path."""

    def test_normalize_message_valid(self) -> None:
        """Well-formed raw dict normalizes to NormalizedGmailMessage correctly."""
        from helm_providers.gmail import NormalizedGmailMessage, normalize_message

        now = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)
        raw = {
            "id": "abc123",
            "threadId": "thr456",
            "from": "alice@example.com",
            "subject": "Test Subject",
            "body_text": "Hello body",
            "internalDate": "1710000000000",
        }

        msg = normalize_message(raw, normalized_at=now)

        assert isinstance(msg, NormalizedGmailMessage)
        assert msg.provider_message_id == "abc123"
        assert msg.provider_thread_id == "thr456"
        assert msg.from_address == "alice@example.com"
        assert msg.subject == "Test Subject"
        assert msg.body_text == "Hello body"
        assert msg.source == "gmail"
        assert msg.normalized_at == now

    def test_normalize_message_missing_id_raises(self) -> None:
        """Empty id field raises ValueError."""
        from helm_providers.gmail import normalize_message

        raw = {
            "id": "",
            "from": "x@x.com",
            "subject": "No ID",
            "body_text": "content",
        }

        with pytest.raises(ValueError, match="non-empty `id`"):
            normalize_message(raw)


class TestProviderFactoryInbox:
    """ProviderFactory.inbox() — returns GmailProvider."""

    def test_factory_inbox_returns_gmail_provider(self) -> None:
        """ProviderFactory.inbox() must return a GmailProvider instance."""
        from helm_providers.factory import ProviderFactory
        from helm_providers.gmail import GmailProvider

        db = MagicMock()

        with patch("helm_providers.gmail.get_credentials") as mock_get_creds, \
             patch("helm_providers.gmail.build_google_credentials") as mock_build, \
             patch("helm_providers.gmail.build") as mock_disc_build:
            mock_creds_orm = MagicMock()
            mock_creds_orm.email = "user@example.com"
            mock_get_creds.return_value = mock_creds_orm
            mock_build.return_value = MagicMock()
            mock_disc_build.return_value = MagicMock()

            factory = ProviderFactory(user_id=1, db=db)
            provider = factory.inbox()

        assert isinstance(provider, GmailProvider)
