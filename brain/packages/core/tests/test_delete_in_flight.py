from collections.abc import AsyncIterator, Sequence

import pytest

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
    SessionDeletedError,
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
    def __init__(self) -> None:
        self.prompts: list[Sequence[Message]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        self.prompts.append(messages)
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


class _DeletedBeforeHistoryRead(InMemorySessionStore):
    """Deletes the chat after the turn's message was stored and before its history is read."""

    async def history(self, session_id: str) -> Sequence[Message]:
        await self.delete(session_id)
        return await super().history(session_id)


@pytest.mark.parametrize(
    ("store", "deleted_first"),
    [(InMemorySessionStore, True), (_DeletedBeforeHistoryRead, False)],
)
async def test_a_turn_in_a_deleted_chat_is_refused_before_the_model_is_asked(
    store: type[InMemorySessionStore], *, deleted_first: bool
) -> None:
    sessions, memories, backend = store(), _CountingAdds(), _AnsweringBackend()
    if deleted_first:
        await sessions.delete(_CHAT)
    engine = TurnEngine(
        sessions,
        backend,
        SystemClock(),
        capabilities=TurnCapabilities(
            memory=MemoryRecaller(memories, HashEmbedder(), SystemClock())
        ),
    )
    with pytest.raises(SessionDeletedError, match="this chat was deleted"):
        async for _event in engine.handle_turn(_CHAT, "Tell me a story.", turn_id="t-d"):
            pass
    assert backend.prompts == []
    assert memories.adds == 0
    assert list(await InMemorySessionStore.history(sessions, _CHAT)) == []
    assert list(await sessions.list_sessions(limit=50)) == []
