"""Memory domain values: what is remembered, and how a retrieval scored it (pure data)."""

from dataclasses import dataclass
from datetime import datetime

# The namespace a memory with no explicit scope belongs to (ADR-0008 scoping addendum).
# One shared space is the v1 behavior, and what ``GlobalMemoryScope`` keeps recall across.
GLOBAL_SCOPE = "global"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One durable memory: its text, the embedding retrieval ranks on, and when it was written.

    ``at`` must be timezone-aware because memory outlives every process and model swap (the one
    hard rule), so a naive timestamp is ambiguous. ``embedding`` is a tuple so the record
    stays immutable and hashable; the caller (``MemoryRecaller``) fills every field, leaving
    the store a pure translator. ``scope`` is the opaque namespace the memory lives in
    (ADR-0008 scoping addendum), ``GLOBAL_SCOPE`` unless the caller's ``MemoryScope`` chose one.
    ``tainted`` is the untrusted-provenance marker (ADR-0019): ``True`` when the exchange was
    recorded from a turn that read untrusted content, so recall fences it as data, not trusted
    context. Defaults ``False``, which is the trusted memory every untainted turn writes.
    """

    id: str
    text: str
    embedding: tuple[float, ...]
    at: datetime
    scope: str = GLOBAL_SCOPE
    tainted: bool = False

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "MemoryRecord.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ScoredMemory:
    """A retrieval hit: the record and its similarity to the query (higher = closer).

    ``score`` is always the store's raw cosine similarity, in ``[-1, 1]``, and never the key a
    ``RecallPolicy`` ranked by (ADR-0008 relevance-field addendum). A reranking policy reorders and
    prunes above the store, so the emitted order is not explained by this field and no caller may
    infer a ranking from it. A second field carrying a policy's own blended relevance is
    deliberately absent: nothing reads a recall score today, and the opt-in policies rank by three
    different quantities, one of them computed against the kept set and so incomparable between
    hits.
    """

    record: MemoryRecord
    score: float
