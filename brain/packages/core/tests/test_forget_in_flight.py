import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    GLOBAL_SCOPE,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    JsonSchema,
    MemoryRecaller,
    MemoryRecord,
    Message,
    SystemClock,
    TaintLedger,
    TextChunk,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.turn_output import FORGOTTEN_RECALL_LOG_MSG, record_exchange

_AT = datetime(2026, 10, 17, 6, 0, 0, tzinfo=UTC)
_CODE = "The shed's padlock code is 4417."

type Interrupt = Callable[[InMemoryMemoryStore], Awaitable[object]]


class _InterruptingBackend:
    """Runs ``interrupt`` on the memory store while it answers, as a turn in another chat would."""

    def __init__(self, store: InMemoryMemoryStore, interrupt: Interrupt | None) -> None:
        self._store = store
        self._interrupt = interrupt

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        if self._interrupt is not None:
            await self._interrupt(self._store)
        yield TextChunk("The code is 4417.")


def _memory(record_id: str, *, tainted: bool, scope: str = GLOBAL_SCOPE) -> MemoryRecord:
    return MemoryRecord(
        id=record_id, text=_CODE, embedding=(1.0,) * 16, at=_AT, scope=scope, tainted=tainted
    )


async def _forget(store: InMemoryMemoryStore) -> object:
    return await store.delete_tainted()


async def _tainted_after_turn(*seeded: MemoryRecord, interrupt: Interrupt | None) -> list[str]:
    store = InMemoryMemoryStore()
    for record in seeded:
        await store.add(record)
    recaller = MemoryRecaller(store, HashEmbedder(), SystemClock(), id_factory=lambda: "answer")
    engine = TurnEngine(
        InMemorySessionStore(),
        _InterruptingBackend(store, interrupt),
        SystemClock(),
        capabilities=TurnCapabilities(memory=recaller, record_tainted_memory=True),
    )
    async for _event in engine.handle_turn(
        "chat-c", "What is the shed's padlock code?", turn_id="t-c"
    ):
        pass
    hits = await store.search((1.0,) * 16, k=50)
    return sorted(hit.record.id for hit in hits if hit.record.tainted)


async def test_a_forget_while_a_turn_answers_from_a_tainted_memory_leaves_no_tainted_row(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex_core.turn_output")
    assert await _tainted_after_turn(_memory("read", tainted=True), interrupt=_forget) == []
    assert FORGOTTEN_RECALL_LOG_MSG in caplog.messages


async def test_a_turn_whose_recalled_memory_is_kept_is_recorded_tainted() -> None:
    assert await _tainted_after_turn(_memory("read", tainted=True), interrupt=None) == [
        "answer",
        "read",
    ]


async def test_deleting_a_trusted_memory_the_turn_recalled_does_not_stop_its_record() -> None:
    async def drop_trusted(store: InMemoryMemoryStore) -> object:
        return await store.delete_scope("elsewhere")

    seeded = (_memory("read", tainted=True), _memory("note", tainted=False, scope="elsewhere"))
    assert await _tainted_after_turn(*seeded, interrupt=drop_trusted) == ["answer", "read"]


async def test_a_turn_tainted_only_by_its_own_reads_is_recorded_whatever_was_forgotten() -> None:
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, HashEmbedder(), SystemClock(), id_factory=lambda: "answer")
    await record_exchange(
        TurnCapabilities(memory=recaller, record_tainted_memory=True),
        TaintLedger(tainted=True),
        store=InMemorySessionStore(),
        session_id="chat-c",
        query="read shed.txt",
        reply="It says 4417.",
        runs=(),
    )
    (hit,) = await store.search((1.0,) * 16, k=5)
    assert (hit.record.id, hit.record.tainted) == ("answer", True)
