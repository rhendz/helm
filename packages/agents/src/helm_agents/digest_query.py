from dataclasses import dataclass
from typing import Protocol

from helm_storage.db import SessionLocal
from helm_storage.repositories import (
    ActionDigestRecord,
    DigestInputRepository,
    DigestItemRecord,
    DraftDigestRecord,
    StudyPriorityRecord,
)


@dataclass(frozen=True)
class DigestInputs:
    open_action_items: list[ActionDigestRecord]
    top_digest_items: list[DigestItemRecord]
    pending_drafts: list[DraftDigestRecord]
    study_priorities: list[StudyPriorityRecord]


class DigestInputProvider(Protocol):
    def fetch_inputs(self) -> DigestInputs: ...


class StorageDigestInputProvider:
    def __init__(self, *, limit_per_source: int = 20) -> None:
        self._limit_per_source = limit_per_source

    def fetch_inputs(self) -> DigestInputs:
        with SessionLocal() as session:
            repository = DigestInputRepository(session)
            return DigestInputs(
                open_action_items=repository.list_open_action_items(self._limit_per_source),
                top_digest_items=repository.list_high_priority_digest_items(self._limit_per_source),
                pending_drafts=repository.list_pending_drafts(self._limit_per_source),
                study_priorities=repository.list_study_priorities(self._limit_per_source),
            )
