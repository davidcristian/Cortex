"""Reference implementations of the ports (pure, deterministic, fully covered).

These are not test-only stubs: EchoInferenceBackend and SystemClock are the real
runtime wiring until Slice 4 delivers an engine adapter, and InMemorySessionStore
is the contract-test twin of the Redis adapter (``cortex_session``).
"""

import hashlib
import math
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError
from cortex_core.memory import MemoryRecord, ScoredMemory

# The fake embedder's default vector width. Small (< a sha256 digest) so distinct texts
# get distinct vectors without cycling the digest; the real nomic model is 768-dim.
_FAKE_EMBED_DIM = 16


class InMemorySessionStore:
    """SessionStore held in a dict and meant for tests and single-process experiments only.

    It intentionally does NOT survive a process restart; the Redis adapter is the
    runtime store precisely because this one cannot prove the hard rule.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}

    async def append(self, session_id: str, message: Message) -> None:
        """Persist one message at the end of the session's history."""
        self._sessions.setdefault(session_id, []).append(message)

    async def history(self, session_id: str) -> Sequence[Message]:
        """Return the session's full history in append order (empty when unknown)."""
        return tuple(self._sessions.get(session_id, ()))


class EchoInferenceBackend:
    """The scripted fake behind CI chat: deterministic, observable state survival.

    For a history whose latest user message has text ``T`` and which contains ``n``
    user messages in total (including the current one), the reply is exactly
    ``"reply {n}: {T}"``, streamed as three deltas. Because ``n`` is derived from
    the store-backed history alone, it keeps counting across a process restart,
    which is what makes external session state observable end to end.
    """

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        """Stream the scripted reply; the logical model id does not alter the script."""
        del model  # routing/config concern; the script is model-independent
        user_messages = [message for message in messages if message.role is Role.USER]
        if not user_messages:
            msg = "EchoInferenceBackend requires at least one user message in the history"
            raise InferenceError(msg)
        yield "reply "
        yield f"{len(user_messages)}:"
        yield f" {user_messages[-1].text}"


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

    async def add(self, record: MemoryRecord) -> None:
        """Persist one memory record."""
        self._records.append(record)

    async def search(self, embedding: Sequence[float], *, k: int) -> Sequence[ScoredMemory]:
        """Return the ``k`` records most similar to ``embedding``, most-similar first."""
        scored = [
            ScoredMemory(record=record, score=_cosine(embedding, record.embedding))
            for record in self._records
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(scored[:k])


class SystemClock:
    """Clock backed by the system time, always timezone-aware UTC."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)
