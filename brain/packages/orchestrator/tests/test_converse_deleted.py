from collections.abc import AsyncIterator

from cortex_core import (
    SESSION_DELETED_MSG,
    EchoInferenceBackend,
    InMemorySessionStore,
    SystemClock,
    TurnEngine,
)
from cortex_orchestrator import ERROR_CODE_SESSION_DELETED, converse
from cortex_seam import ClientEvent, ServerEvent, UserTurn


async def _events_from(*events: ClientEvent) -> AsyncIterator[ClientEvent]:
    for event in events:
        yield event


async def _turns(engine: TurnEngine, *session_ids: str) -> list[ServerEvent]:
    turns = (ClientEvent(session_id=s, user_turn=UserTurn(text="hi")) for s in session_ids)
    return [event async for event in converse(lambda _c, _p: engine, _events_from(*turns))]


async def test_a_turn_sent_to_a_deleted_chat_ends_the_stream_as_session_deleted() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    await _turns(engine, "old")
    await store.delete("old")
    events = await _turns(engine, "old", "new")
    assert [event.WhichOneof("event") for event in events] == ["error"]
    assert events[0].error.code == ERROR_CODE_SESSION_DELETED
    assert events[0].error.message == SESSION_DELETED_MSG
    assert await store.history("old") == ()
    assert await store.history("new") == ()


async def test_a_new_chat_on_a_new_stream_is_answered_after_a_refusal() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    await store.delete("old")
    await _turns(engine, "old")
    events = await _turns(engine, "new")
    assert [event.WhichOneof("event") for event in events][-1] == "turn_complete"
    assert len(await store.history("new")) == 2
