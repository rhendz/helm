"""Unit tests for GoogleCalendarAuth credential management."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from helm_connectors.google_calendar import GoogleCalendarAuth


class TestGoogleCalendarAuthInit:
    """Tests for GoogleCalendarAuth.__init__ and credential initialization."""

    def test_init_success_with_valid_env_vars(self) -> None:
        """Successful initialization with all required env vars present."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-client-id-123",
                "GOOGLE_CLIENT_SECRET": "test-client-secret-456",
                "GOOGLE_REFRESH_TOKEN": "test-refresh-token-789",
            },
        ):
            auth = GoogleCalendarAuth()
            assert auth._client_id == "test-client-id-123"
            assert auth._client_secret == "test-client-secret-456"
            assert auth._refresh_token == "test-refresh-token-789"
            assert auth._credentials is not None

    def test_init_failure_missing_client_id(self) -> None:
        """Initialization fails when GOOGLE_CLIENT_ID is missing."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
            clear=False,
        ):
            with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
                GoogleCalendarAuth()

    def test_init_failure_missing_client_secret(self) -> None:
        """Initialization fails when GOOGLE_CLIENT_SECRET is missing."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
            clear=False,
        ):
            with pytest.raises(ValueError, match="GOOGLE_CLIENT_SECRET"):
                GoogleCalendarAuth()

    def test_init_failure_missing_refresh_token(self) -> None:
        """Initialization fails when GOOGLE_REFRESH_TOKEN is missing."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "",
            },
            clear=False,
        ):
            with pytest.raises(ValueError, match="GOOGLE_REFRESH_TOKEN"):
                GoogleCalendarAuth()

    def test_credentials_initialized_with_refresh_token(self) -> None:
        """Credentials object is initialized with refresh_token but no access token."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds_instance = MagicMock()
                mock_creds_class.return_value = mock_creds_instance

                GoogleCalendarAuth()

                # Verify Credentials was called with correct parameters
                mock_creds_class.assert_called_once_with(
                    token=None,
                    refresh_token="test-token",
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id="test-id",
                    client_secret="test-secret",
                    scopes=["https://www.googleapis.com/auth/calendar"],
                )


class TestGoogleCalendarAuthRefresh:
    """Tests for GoogleCalendarAuth.get_refreshed_credentials and token refresh."""

    def test_refresh_success_on_first_call(self) -> None:
        """Token refresh succeeds and returns credentials with valid access_token."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds.expired = True
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request") as mock_request_class:
                    mock_request = MagicMock()
                    mock_request_class.return_value = mock_request

                    auth = GoogleCalendarAuth()
                    result = auth.get_refreshed_credentials()

                    # Verify refresh was called
                    mock_creds.refresh.assert_called_once_with(mock_request)
                    assert result is mock_creds

    def test_refresh_multiple_calls(self) -> None:
        """Multiple refresh calls work correctly."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request"):
                    auth = GoogleCalendarAuth()
                    
                    # First refresh
                    result1 = auth.get_refreshed_credentials()
                    assert mock_creds.refresh.call_count == 1
                    
                    # Second refresh
                    result2 = auth.get_refreshed_credentials()
                    assert mock_creds.refresh.call_count == 2
                    assert result1 is result2

    def test_refresh_failure_invalid_grant(self) -> None:
        """Refresh fails with ValueError when refresh_token is invalid (invalid_grant)."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "invalid-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                # Simulate invalid_grant error from Google API
                mock_creds.refresh.side_effect = ValueError(
                    "invalid_grant: Token has been revoked"
                )
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request"):
                    auth = GoogleCalendarAuth()
                    
                    with pytest.raises(ValueError, match="credential refresh failed"):
                        auth.get_refreshed_credentials()

    def test_refresh_failure_network_error(self) -> None:
        """Refresh fails with RuntimeError when network/server error occurs."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                # Simulate network/connection error
                mock_creds.refresh.side_effect = RuntimeError(
                    "Connection timeout"
                )
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request"):
                    auth = GoogleCalendarAuth()
                    
                    with pytest.raises(RuntimeError, match="credential refresh failed"):
                        auth.get_refreshed_credentials()

    def test_refresh_failure_http_5xx(self) -> None:
        """Refresh fails with RuntimeError on HTTP 5xx from Google API."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                # Simulate 5xx response
                mock_creds.refresh.side_effect = Exception(
                    "500 Internal Server Error from https://oauth2.googleapis.com/token"
                )
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request"):
                    auth = GoogleCalendarAuth()
                    
                    with pytest.raises(RuntimeError, match="credential refresh failed"):
                        auth.get_refreshed_credentials()

    def test_refresh_logs_expiry_status(self) -> None:
        """Refresh logs the expiry status before attempting refresh."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds.expired = True
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request"):
                    with patch("helm_connectors.google_calendar.logger") as mock_logger:
                        auth = GoogleCalendarAuth()
                        auth.get_refreshed_credentials()
                        
                        # Verify logger called with refresh_attempt and success
                        calls = mock_logger.info.call_args_list
                        call_messages = [call[0][0] for call in calls]
                        assert "calendar_credential_refresh_attempt" in call_messages
                        assert "calendar_credential_refreshed" in call_messages

    def test_refresh_logs_error_on_failure(self) -> None:
        """Refresh logs detailed error information on failure."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "invalid-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds.refresh.side_effect = ValueError(
                    "invalid_grant: Token has been revoked"
                )
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request"):
                    with patch("helm_connectors.google_calendar.logger") as mock_logger:
                        auth = GoogleCalendarAuth()
                        
                        with pytest.raises(ValueError):
                            auth.get_refreshed_credentials()
                        
                        # Verify error was logged
                        mock_logger.error.assert_called()


class TestGoogleCalendarAuthEnvVarHandling:
    """Tests for environment variable extraction and validation."""

    def test_env_var_with_whitespace_is_stripped(self) -> None:
        """Environment variables with leading/trailing whitespace are stripped."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "  test-id-with-spaces  ",
                "GOOGLE_CLIENT_SECRET": "\ttest-secret\t",
                "GOOGLE_REFRESH_TOKEN": " test-token ",
            },
        ):
            auth = GoogleCalendarAuth()
            assert auth._client_id == "test-id-with-spaces"
            assert auth._client_secret == "test-secret"
            assert auth._refresh_token == "test-token"

    def test_env_var_only_whitespace_treated_as_missing(self) -> None:
        """Environment variables containing only whitespace are treated as missing."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "   ",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
            clear=False,
        ):
            with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
                GoogleCalendarAuth()

    def test_all_three_env_vars_required(self) -> None:
        """All three environment variables must be present (no partial init)."""
        # Test missing one at a time
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
            clear=False,
        ):
            with pytest.raises(ValueError):
                GoogleCalendarAuth()


class TestGoogleCalendarAuthTokenExpiry:
    """Tests for token expiry detection and refresh triggering."""

    def test_credentials_expired_property_checked(self) -> None:
        """Refresh checks and logs the expired property of credentials."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds.expired = True  # Token is expired
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request"):
                    with patch("helm_connectors.google_calendar.logger"):
                        auth = GoogleCalendarAuth()
                        auth.get_refreshed_credentials()
                        
                        # Refresh should have been called
                        mock_creds.refresh.assert_called_once()

    def test_credentials_not_expired_still_refreshes(self) -> None:
        """Refresh is always called regardless of expired property (defensive)."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "test-id",
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REFRESH_TOKEN": "test-token",
            },
        ):
            with patch("google.oauth2.credentials.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds.expired = False  # Token is not expired
                mock_creds_class.return_value = mock_creds

                with patch("google.auth.transport.requests.Request"):
                    auth = GoogleCalendarAuth()
                    auth.get_refreshed_credentials()
                    
                    # Refresh should still be called
                    mock_creds.refresh.assert_called_once()
