"""Memory domain values: what is remembered, and how a retrieval scored it (pure data)."""

from dataclasses import dataclass
from datetime import datetime

# The namespace a memory with no explicit scope belongs to (ADR-0008 scoping addendum).
# One shared space is the v1 behavior, and what ``GlobalMemoryScope`` keeps recall across.
GLOBAL_SCOPE = "global"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One durable memory: its text, the embedding retrieval ranks on, and when it was written."""

    id: str
    text: str
    embedding: tuple[float, ...]
    at: datetime
    scope: str = GLOBAL_SCOPE

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "MemoryRecord.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ScoredMemory:
    """A retrieval hit: the record and its similarity to the query (higher = closer)."""

    record: MemoryRecord
    score: float
