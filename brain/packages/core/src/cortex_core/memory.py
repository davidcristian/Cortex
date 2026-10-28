"""Memory domain values: what is remembered, and how a retrieval scored it (pure data)."""

from dataclasses import dataclass
from datetime import datetime

GLOBAL_SCOPE = "global"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One durable memory: its text, the embedding retrieval ranks on, when and by which session.

    ``session_id`` is None for a memory stored before the writing session was recorded.
    """

    id: str
    text: str
    embedding: tuple[float, ...]
    at: datetime
    scope: str = GLOBAL_SCOPE
    tainted: bool = False
    session_id: str | None = None

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "MemoryRecord.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ScoredMemory:
    """A retrieval hit: the record and its similarity to the query (higher = closer)."""

    record: MemoryRecord
    score: float
