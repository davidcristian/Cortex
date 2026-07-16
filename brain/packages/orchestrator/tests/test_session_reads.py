"""The read-only session RPCs over a real loopback grpc.aio server (ADR-0021, CI-safe).

ListSessions and GetSessionMessages are views of the store the overlay's chat list,
switcher, and cycling load from. A failing store aborts the unary RPC UNAVAILABLE.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

import grpc
import pytest
from grpc import aio

from cortex_core import (
    EchoInferenceBackend,
    InMemorySessionStore,
    Message,
    Role,
    SessionStore,
    SessionStoreError,
    SessionSummary,
    SystemClock,
    TurnEngine,
)
from cortex_orchestrator import (
    DEFAULT_SESSION_LIST_LIMIT,
    SeamServerConfig,
    create_server,
)
from cortex_seam import (
    BrainServiceStub,
    GetSessionMessagesReply,
    GetSessionMessagesRequest,
    ListSessionsReply,
    ListSessionsRequest,
)

_T0 = datetime(2026, 7, 8, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
_T2 = datetime(2026, 7, 8, 11, 0, tzinfo=UTC)


# The generated stub attributes are untyped wire code (gate-exempt, ADR-0002 d4); these
# helpers pin the reply types once so the tests below stay fully typed.
async def _list(stub: BrainServiceStub, limit: int) -> ListSessionsReply:
    method = stub.ListSessions  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("ListSessionsReply", await method(ListSessionsRequest(limit=limit)))


async def _messages(stub: BrainServiceStub, session_id: str) -> GetSessionMessagesReply:
    method = stub.GetSessionMessages  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "GetSessionMessagesReply",
        await method(GetSessionMessagesRequest(session_id=session_id)),
    )


async def _serve(store: SessionStore) -> tuple[aio.Server, str]:
    """A BrainService over `store` on an ephemeral loopback port."""
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    server, port = create_server(
        SeamServerConfig(host="127.0.0.1", port=0), lambda _confirmer, _progress: engine, store
    )
    await server.start()
    return server, f"127.0.0.1:{port}"


def _msg(role: Role, text: str, at: datetime) -> Message:
    return Message(role=role, text=text, at=at, turn_id="t")


async def _seeded_store() -> InMemorySessionStore:
    """Two chats: 'alpha' (older, two messages) and 'beta' (newer, one message)."""
    store = InMemorySessionStore()
    await store.append("alpha", _msg(Role.USER, "about cats", _T0))
    await store.append("alpha", _msg(Role.ASSISTANT, "cats are great", _T1))
    await store.append("beta", _msg(Role.USER, "about dogs", _T2))
    return store


async def test_list_sessions_returns_summaries_newest_first_with_unix_ms() -> None:
    store = await _seeded_store()
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _list(BrainServiceStub(channel), limit=0)
    finally:
        await server.stop(grace=None)
    assert [s.session_id for s in reply.sessions] == ["beta", "alpha"]
    alpha = reply.sessions[1]
    assert alpha.title == "about cats"
    assert alpha.preview == "cats are great"
    assert alpha.last_activity_unix_ms == int(_T1.timestamp() * 1000)


async def test_list_sessions_zero_limit_uses_the_server_default() -> None:
    # With three sessions and a 0 limit → the default (well above 3) → all three back.
    store = await _seeded_store()
    await store.append("gamma", _msg(Role.USER, "about birds", _T2))
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _list(BrainServiceStub(channel), limit=0)
    finally:
        await server.stop(grace=None)
    assert len(reply.sessions) == 3
    assert DEFAULT_SESSION_LIST_LIMIT >= 3


async def test_list_sessions_positive_limit_caps_the_count() -> None:
    store = await _seeded_store()
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _list(BrainServiceStub(channel), limit=1)
    finally:
        await server.stop(grace=None)
    assert [s.session_id for s in reply.sessions] == ["beta"]  # the single newest


async def test_get_session_messages_returns_the_history_in_order() -> None:
    store = await _seeded_store()
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _messages(BrainServiceStub(channel), "alpha")
    finally:
        await server.stop(grace=None)
    assert [(m.role, m.text) for m in reply.messages] == [
        ("user", "about cats"),
        ("assistant", "cats are great"),
    ]
    assert reply.messages[0].turn_id == "t"
    assert reply.messages[1].at_unix_ms == int(_T1.timestamp() * 1000)


async def test_get_session_messages_for_an_unknown_session_is_empty() -> None:
    server, address = await _serve(InMemorySessionStore())
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _messages(BrainServiceStub(channel), "never-seen")
    finally:
        await server.stop(grace=None)
    assert list(reply.messages) == []


class FailingStore:
    """A SessionStore whose reads raise, to drive the handlers' UNAVAILABLE abort path."""

    async def append(self, session_id: str, message: Message) -> None:
        del session_id, message

    async def history(self, session_id: str) -> Sequence[Message]:
        del session_id
        msg = "redis is down"
        raise SessionStoreError(msg)

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        del limit
        msg = "redis is down"
        raise SessionStoreError(msg)

    async def set_title(self, session_id: str, title: str) -> None:
        del session_id, title


async def test_list_sessions_store_failure_aborts_unavailable() -> None:
    server, address = await _serve(FailingStore())
    try:
        async with aio.insecure_channel(address) as channel:
            with pytest.raises(aio.AioRpcError) as excinfo:
                await _list(BrainServiceStub(channel), limit=10)
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() is grpc.StatusCode.UNAVAILABLE
    assert "redis is down" in (excinfo.value.details() or "")


async def test_get_session_messages_store_failure_aborts_unavailable() -> None:
    server, address = await _serve(FailingStore())
    try:
        async with aio.insecure_channel(address) as channel:
            with pytest.raises(aio.AioRpcError) as excinfo:
                await _messages(BrainServiceStub(channel), "alpha")
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() is grpc.StatusCode.UNAVAILABLE
