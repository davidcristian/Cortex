import asyncio
import logging
from collections.abc import AsyncIterator, Sequence

import pytest

from cortex_core import (
    EchoInferenceBackend,
    HashEmbedder,
    InMemoryMemoryStore,
    InMemorySessionStore,
    MemoryRecaller,
    SystemClock,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
    TurnEvent,
)


class StallingEmbedder:
    """Embeds the first ``answered`` texts, then never answers, as a frozen server does."""

    def __init__(self, answered: int) -> None:
        self._inner = HashEmbedder()
        self._answered = answered
        self.calls = 0

    async def embed(self, text: str) -> Sequence[float]:
        self.calls += 1
        if self.calls > self._answered:
            await asyncio.Event().wait()
        return await self._inner.embed(text)


async def _collect(events: AsyncIterator[TurnEvent]) -> list[TurnEvent]:
    return [event async for event in events]


def _engine(
    embedder: StallingEmbedder, memories: InMemoryMemoryStore, *, timeout_s: float
) -> tuple[TurnEngine, InMemorySessionStore]:
    store = InMemorySessionStore()
    recaller = MemoryRecaller(memories, embedder, SystemClock())
    caps = TurnCapabilities(memory=recaller, memory_write_timeout_s=timeout_s)
    return TurnEngine(store, EchoInferenceBackend(), SystemClock(), capabilities=caps), store


async def test_a_frozen_embedder_ends_the_write_at_the_bound_and_the_turn_completes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    embedder = StallingEmbedder(answered=1)
    memories = InMemoryMemoryStore()
    engine, store = _engine(embedder, memories, timeout_s=0.05)

    with caplog.at_level(logging.ERROR, logger="cortex_core.turn_output"):
        events = await asyncio.wait_for(_collect(engine.handle_turn("s", "hi", turn_id="t-1")), 5)

    assert isinstance(events[-1], TurnCompleted)
    assert [m.text for m in await store.history("s")] == ["hi", events[-1].full_text]
    assert embedder.calls == 2
    assert await memories.count_candidates() == 0
    assert [r.message for r in caplog.records] == [
        "memory write unavailable; this exchange was not recorded to memory"
    ]
    assert caplog.records[0].exc_info is not None
    assert caplog.records[0].exc_info[0] is TimeoutError


async def test_a_write_inside_the_bound_is_recorded() -> None:
    embedder = StallingEmbedder(answered=2)
    memories = InMemoryMemoryStore()
    engine, _ = _engine(embedder, memories, timeout_s=5.0)

    await _collect(engine.handle_turn("s", "hi", turn_id="t-1"))

    assert await memories.count_candidates() == 1
