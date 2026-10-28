"""In-memory fakes for the three memory-area ports: Embedder, MemoryStore, RecallAuditSink."""

import hashlib
import math
from collections.abc import Sequence

from cortex_core.embed_input import EMBED_INPUT_CHARS
from cortex_core.errors import EmbedderError, MemoryStoreError
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.ranking import RecallAudit

# Under the 32 bytes of a sha256 digest, so no byte is reused and distinct texts get distinct
# vectors. The real embedding model returns 768 values.
_FAKE_EMBED_DIM = 16


class HashEmbedder:
    """Deterministic, I/O-free Embedder for CI and the memory use-case tests."""

    def __init__(
        self, dimension: int = _FAKE_EMBED_DIM, *, max_chars: int = EMBED_INPUT_CHARS
    ) -> None:
        self._dimension = dimension
        self._max_chars = max_chars
        self._failure: EmbedderError | None = None

    async def embed(self, text: str) -> Sequence[float]:
        """Return the deterministic pseudo-embedding of ``text``, or the scripted failure."""
        if self._failure is not None:
            raise self._failure
        if len(text) > self._max_chars:
            msg = f"an input of {len(text)} characters is over this embedder's {self._max_chars}"
            raise EmbedderError(msg)
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

    async def add(self, record: MemoryRecord, *, recalled: Sequence[str] = ()) -> bool:
        """Persist ``record`` only while every id in ``recalled`` is still stored."""
        self._guard()
        stored = {kept.id for kept in self._records}
        if not set(recalled) <= stored:
            return False
        self._records.append(record)
        return True

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

    async def find_text(
        self, text: str, *, limit: int, scopes: Sequence[str] | None = None
    ) -> Sequence[MemoryRecord]:
        """The first ``limit`` memories of ``scopes`` whose text contains ``text``, case ignored."""
        self._guard()
        needle = text.lower()
        found = [record for record in self._in_scopes(scopes) if needle in record.text.lower()]
        found.sort(key=lambda record: (record.at, record.id))
        return tuple(found[:limit])

    async def count_tainted(self, *, scopes: Sequence[str] | None = None) -> int:
        """How many tainted memories ``scopes`` holds."""
        self._guard()
        return sum(1 for record in self._in_scopes(scopes) if record.tainted)

    async def delete_scope(self, scope: str) -> int:
        """Hard-delete every memory in ``scope``; return how many were removed (0 if none)."""
        self._guard()
        kept = [record for record in self._records if record.scope != scope]
        removed = len(self._records) - len(kept)
        self._records = kept
        return removed

    async def delete_tainted(self, *, scopes: Sequence[str] | None = None) -> int:
        """Hard-delete every tainted memory in ``scopes``; return how many were removed."""
        self._guard()
        doomed = {id(record) for record in self._in_scopes(scopes) if record.tainted}
        self._records = [record for record in self._records if id(record) not in doomed]
        return len(doomed)

    async def delete_ids(self, ids: Sequence[str]) -> int:
        """Hard-delete the memories whose ids are in ``ids``; return how many were removed."""
        self._guard()
        doomed = set(ids)
        kept = [record for record in self._records if record.id not in doomed]
        removed = len(self._records) - len(kept)
        self._records = kept
        return removed

    async def delete_written_by(self, session_id: str) -> int:
        """Hard-delete every memory ``session_id`` wrote, in any scope; return how many."""
        self._guard()
        kept = [record for record in self._records if record.session_id != session_id]
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
