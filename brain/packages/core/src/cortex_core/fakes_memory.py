"""In-memory fakes for the three memory-area ports: Embedder, MemoryStore, RecallAuditSink."""

import hashlib
import math
from collections.abc import Sequence

from cortex_core.errors import EmbedderError, MemoryStoreError
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.ranking import RecallAudit

# Under the 32 bytes of a sha256 digest, so no byte is reused and distinct texts get distinct
# vectors. The real embedding model returns 768 values.
_FAKE_EMBED_DIM = 16


class HashEmbedder:
    """Deterministic, I/O-free Embedder for CI and the memory use-case tests."""

    def __init__(self, dimension: int = _FAKE_EMBED_DIM) -> None:
        self._dimension = dimension
        self._failure: EmbedderError | None = None

    async def embed(self, text: str) -> Sequence[float]:
        """Return the deterministic pseudo-embedding of ``text``, or the scripted failure."""
        if self._failure is not None:
            raise self._failure
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return tuple(float(digest[i % len(digest)]) - 127.5 for i in range(self._dimension))

    def fail_with(self, error: EmbedderError) -> None:
        """Make every later ``embed`` raise ``error``: a backend taken away mid-run."""
        self._failure = error


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either has no magnitude."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    if magnitude == 0:
        return 0.0
    return dot / magnitude


class InMemoryMemoryStore:
    """MemoryStore held in a list and meant for tests and single-process experiments only."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []
        self._failure: MemoryStoreError | None = None

    def fail_with(self, error: MemoryStoreError) -> None:
        """Make every later call raise ``error``: a backend taken away mid-run."""
        self._failure = error

    def _guard(self) -> None:
        """Raise the scripted failure, if one was set, before any method does its work."""
        if self._failure is not None:
            raise self._failure

    def _in_scopes(self, scopes: Sequence[str] | None) -> list[MemoryRecord]:
        """The records ``scopes`` selects, which ``search`` ranks and ``count_candidates`` sums."""
        allowed = None if scopes is None else set(scopes)
        return [record for record in self._records if allowed is None or record.scope in allowed]

    async def add(self, record: MemoryRecord) -> None:
        """Persist one memory record."""
        self._guard()
        self._records.append(record)

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        """Return the ``k`` records most similar to ``embedding``, most-similar first."""
        self._guard()
        scored = [
            ScoredMemory(record=record, score=_cosine(embedding, record.embedding))
            for record in self._in_scopes(scopes)
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(scored[:k])

    async def count_candidates(self, *, scopes: Sequence[str] | None = None) -> int:
        """How many memories ``scopes`` holds, whatever ``k`` a search of them would return."""
        self._guard()
        return len(self._in_scopes(scopes))

    async def delete_scope(self, scope: str) -> int:
        """Hard-delete every memory in ``scope``; return how many were removed (0 if none)."""
        self._guard()
        kept = [record for record in self._records if record.scope != scope]
        removed = len(self._records) - len(kept)
        self._records = kept
        return removed


class RecordingRecallSink:
    """RecallAuditSink that keeps audits in a list so tests can assert the recall trail."""

    def __init__(self) -> None:
        self._audits: list[RecallAudit] = []

    async def record(self, audit: RecallAudit) -> None:
        """Append one recall audit to the recorded trail."""
        self._audits.append(audit)

    @property
    def audits(self) -> Sequence[RecallAudit]:
        """The recalls audited so far, in order."""
        return tuple(self._audits)
