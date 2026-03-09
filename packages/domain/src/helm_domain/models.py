from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ActionItem:
    id: str
    title: str
    status: str
    priority: int
    created_at: datetime


# TODO(v1-phase1): expand dataclasses/value objects to match final schema.
