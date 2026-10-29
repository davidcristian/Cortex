from collections.abc import AsyncIterator, Sequence

from cortex_core import (
    GLOBAL_MEMORY_SCOPE,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    JsonSchema,
    MemoryRecaller,
    MemoryRecord,
    Message,
    SessionMemoryCascade,
    SystemClock,
    TextChunk,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)

_CHAT = "chat-d"


class _DeletingBackend:
    """Deletes the chat, as the user's delete would, while the cortex is still answering."""

    def __init__(self, sessions: InMemorySessionStore, memories: InMemoryMemoryStore) -> None:
        self._sessions = sessions
        self._cascade = SessionMemoryCascade(memories, GLOBAL_MEMORY_SCOPE)

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
        await self._sessions.delete(_CHAT)
        await self._cascade.delete_session_memories(_CHAT)
        yield TextChunk("A story about a lighthouse keeper.")


class _AnsweringBackend:
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
        yield TextChunk("A story about a lighthouse keeper.")


class _CountingAdds(InMemoryMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.adds = 0

    async def add(self, record: MemoryRecord, *, recalled: Sequence[str] = ()) -> bool:
        self.adds += 1
        return await super().add(record, recalled=recalled)


class _DeletedBeforeCommit(InMemoryMemoryStore):
    """Runs the chat's whole delete after the record's row was read for and before it is stored."""

    def __init__(self, sessions: InMemorySessionStore) -> None:
        super().__init__()
        self._sessions = sessions

    async def add(self, record: MemoryRecord, *, recalled: Sequence[str] = ()) -> bool:
        await self._sessions.delete(_CHAT)
        await self.delete_written_by(_CHAT)
        return await super().add(record, recalled=recalled)


async def _turn(
    sessions: InMemorySessionStore, memories: InMemoryMemoryStore, *, deleting: bool
) -> list[str]:
    backend = _DeletingBackend(sessions, memories) if deleting else _AnsweringBackend()
    engine = TurnEngine(
        sessions,
        backend,
        SystemClock(),
        capabilities=TurnCapabilities(
            memory=MemoryRecaller(memories, HashEmbedder(), SystemClock())
        ),
    )
    async for _event in engine.handle_turn(_CHAT, "My locker code is 5813.", turn_id="t-d"):
        pass
    return [hit.record.text for hit in await memories.search((1.0,) * 16, k=50)]


async def test_a_chat_deleted_while_its_turn_answers_stays_deleted_with_no_memory() -> None:
    sessions, memories = InMemorySessionStore(), _CountingAdds()
    assert await _turn(sessions, memories, deleting=True) == []
    assert memories.adds == 0
    assert list(await sessions.history(_CHAT)) == []
    assert list(await sessions.list_sessions(limit=50)) == []


async def test_a_row_stored_after_the_delete_removed_the_chats_rows_is_removed() -> None:
    sessions = InMemorySessionStore()
    memories = _DeletedBeforeCommit(sessions)
    assert await _turn(sessions, memories, deleting=False) == []
    assert list(await sessions.list_sessions(limit=50)) == []


async def test_a_turn_in_a_chat_that_was_not_deleted_keeps_its_memory() -> None:
    sessions, memories = InMemorySessionStore(), InMemoryMemoryStore()
    (row,) = await _turn(sessions, memories, deleting=False)
    assert "5813" in row
    assert len(await sessions.history(_CHAT)) == 2
