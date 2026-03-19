"""helm_providers — credential-aware Google provider layer for Helm.

Public surface exported from this package:

Protocols (structural typing, for type annotations):
  - ``CalendarProvider``
  - ``InboxProvider``

Credential helper:
  - ``build_google_credentials``

Factory:
  - ``ProviderFactory``

Concrete providers:
  - ``GoogleCalendarProvider``
  - ``GmailProvider``

Gmail types (re-exported so consumers can import from either
``helm_providers`` or ``helm_providers.gmail``):
  - ``NormalizedGmailMessage``
  - ``PullMessagesReport``
  - ``GmailSendResult``
  - ``GmailSendError``
"""

from helm_providers.credentials import build_google_credentials
from helm_providers.factory import ProviderFactory
from helm_providers.gmail import (
    GmailProvider,
    GmailSendError,
    GmailSendResult,
    NormalizedGmailMessage,
    PullMessagesReport,
)
from helm_providers.google_calendar import GoogleCalendarProvider
from helm_providers.protocols import CalendarProvider, InboxProvider

__all__ = [
    "build_google_credentials",
    "CalendarProvider",
    "GmailProvider",
    "GmailSendError",
    "GmailSendResult",
    "GoogleCalendarProvider",
    "InboxProvider",
    "NormalizedGmailMessage",
    "ProviderFactory",
    "PullMessagesReport",
]
