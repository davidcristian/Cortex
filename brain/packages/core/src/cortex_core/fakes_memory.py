"""In-memory fakes for the three memory-area ports: Embedder, MemoryStore, RecallAuditSink.

Split out of ``fakes.py`` to keep it under the line cap as ``MemoryStore`` grew its
``count_candidates`` verb (the ``fakes_session``/``fakes_body`` precedent), and because these
three belong together: a recall test needs an embedder, a store and somewhere for the trail to
land, and nothing else in ``fakes.py`` participates. Like every in-memory twin here they do NOT
survive a process restart; the pgvector adapter is what proves the durable half, and these only
have to be observably interchangeable with it behind the ports.
"""

import hashlib
import math
from collections.abc import Sequence

from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.ranking import RecallAudit

# The fake embedder's default vector width. Small (< a sha256 digest) so distinct texts
# get distinct vectors without cycling the digest; the real nomic model is 768-dim.
_FAKE_EMBED_DIM = 16


class HashEmbedder:
    """Deterministic, I/O-free Embedder for CI and the memory use-case tests.

    Maps text to a fixed-dimension vector via a stable hash: identical text always yields
    the identical vector (so a stored memory is its own strongest cosine match), distinct
    text yields a distinct vector. It carries NO semantics. The real nomic adapter (Slice
    5 host half) is what makes similarity meaningful. Never emits an all-zero vector (each
    component is an integer byte minus 127.5, never exactly zero).
    """

    def __init__(self, dimension: int = _FAKE_EMBED_DIM) -> None:
        self._dimension = dimension

    async def embed(self, text: str) -> Sequence[float]:
        """Return the deterministic pseudo-embedding of ``text``."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return tuple(float(digest[i % len(digest)]) - 127.5 for i in range(self._dimension))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either has no magnitude."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    if magnitude == 0:
        return 0.0
    return dot / magnitude


class InMemoryMemoryStore:
    """MemoryStore held in a list and meant for tests and single-process experiments only.

    Ranks by cosine similarity in Python; it is the behavioral twin of the pgvector adapter
    (Slice 5 host half) behind the same contract. Like ``InMemorySessionStore`` it does NOT
    survive a restart. The durable store is what proves the hard rule.
    """

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def _in_scopes(self, scopes: Sequence[str] | None) -> list[MemoryRecord]:
        """The candidate set ``scopes`` selects, which ``search`` ranks and ``count`` sizes."""
        allowed = None if scopes is None else set(scopes)
        return [record for record in self._records if allowed is None or record.scope in allowed]

    async def add(self, record: MemoryRecord) -> None:
        """Persist one memory record."""
        self._records.append(record)

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        """Return the ``k`` records most similar to ``embedding``, most-similar first.

        ``scopes`` restricts the candidate set to those namespaces (the pgvector
        ``WHERE scope = ANY`` twin, ADR-0008 addendum); ``None`` ranks over all memories.
        """
        scored = [
            ScoredMemory(record=record, score=_cosine(embedding, record.embedding))
            for record in self._in_scopes(scopes)
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(scored[:k])

    async def count_candidates(self, *, scopes: Sequence[str] | None = None) -> int:
        """How many memories ``scopes`` holds, whatever ``k`` a search of them would return.

        The in-memory twin of the pgvector ``SELECT count(*)`` (ADR-0038 candidate-count
        addendum). It counts the same candidate set ``search`` would rank and is deliberately
        not derived from any search result: a length over returned rows is exactly the answer
        this verb exists to replace.
        """
        return len(self._in_scopes(scopes))

    async def delete_scope(self, scope: str) -> int:
        """Hard-delete every memory in ``scope``; return how many were removed (0 if none).

        The in-memory twin of the pgvector ``DELETE FROM memories WHERE scope = $1`` (ADR-0008
        delete-scope addendum): a removed memory simply stops being a search candidate.
        """
        kept = [record for record in self._records if record.scope != scope]
        removed = len(self._records) - len(kept)
        self._records = kept
        return removed


class RecordingRecallSink:
    """RecallAuditSink that keeps audits in a list so tests can assert the recall trail.

    The shipped adapter writes structured logs and deliberately drops the query and the recalled
    text (ADR-0038 decision 5); this one keeps the whole audit, because a test asserting which key
    a policy ranked by has to be able to read it back.
    """

    def __init__(self) -> None:
        self._audits: list[RecallAudit] = []

    async def record(self, audit: RecallAudit) -> None:
        """Append one recall audit to the recorded trail."""
        self._audits.append(audit)

    @property
    def audits(self) -> Sequence[RecallAudit]:
        """The recalls audited so far, in order."""
        return tuple(self._audits)
