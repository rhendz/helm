from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class EmailMessage:
    provider_message_id: str
    provider_thread_id: str
    from_address: str
    subject: str
    body_text: str
    received_at: datetime
    normalized_at: datetime
    source: str = "gmail"
