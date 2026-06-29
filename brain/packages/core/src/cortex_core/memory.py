"""Memory domain values: what is remembered, and how a retrieval scored it (pure data)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One durable memory: its text, the embedding retrieval ranks on, and when it was written."""

    id: str
    text: str
    embedding: tuple[float, ...]
    at: datetime

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "MemoryRecord.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ScoredMemory:
    """A retrieval hit: the record and its similarity to the query (higher = closer)."""

    record: MemoryRecord
    score: float
