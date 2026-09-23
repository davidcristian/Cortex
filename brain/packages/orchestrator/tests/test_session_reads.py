from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

import grpc
import pytest
from grpc import aio

from cortex_core import (
    EchoInferenceBackend,
    InMemoryMemoryStore,
    InMemorySessionStore,
    MemoryDataError,
    MemoryRecord,
    MemoryStoreError,
    Message,
    Role,
    ScoredMemory,
    SessionMemoryCascade,
    SessionMemoryScope,
    SessionStore,
    SessionStoreError,
    SessionSummary,
    SystemClock,
    TurnEngine,
)
from cortex_core.sessions import HistoryRecap
from cortex_orchestrator import (
    DEFAULT_SESSION_LIST_LIMIT,
    RpcPorts,
    RpcServerConfig,
    create_server,
)
from cortex_seam import (
    BrainServiceStub,
    DeleteSessionReply,
    DeleteSessionRequest,
    GetSessionMessagesReply,
    GetSessionMessagesRequest,
    ListSessionsReply,
    ListSessionsRequest,
    RenameSessionReply,
    RenameSessionRequest,
    SetSessionHoistedReply,
    SetSessionHoistedRequest,
)

_T0 = datetime(2026, 7, 8, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
_T2 = datetime(2026, 7, 8, 11, 0, tzinfo=UTC)


async def _list(stub: BrainServiceStub, limit: int) -> ListSessionsReply:
    method = stub.ListSessions  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("ListSessionsReply", await method(ListSessionsRequest(limit=limit)))


async def _messages(stub: BrainServiceStub, session_id: str) -> GetSessionMessagesReply:
    method = stub.GetSessionMessages  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "GetSessionMessagesReply",
        await method(GetSessionMessagesRequest(session_id=session_id)),
    )


async def _rename(stub: BrainServiceStub, session_id: str, title: str) -> RenameSessionReply:
    method = stub.RenameSession  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "RenameSessionReply",
        await method(RenameSessionRequest(session_id=session_id, title=title)),
    )


async def _delete(stub: BrainServiceStub, session_id: str) -> DeleteSessionReply:
    method = stub.DeleteSession  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("DeleteSessionReply", await method(DeleteSessionRequest(session_id=session_id)))


async def _set_hoisted(
    stub: BrainServiceStub, session_id: str, *, hoisted: bool
) -> SetSessionHoistedReply:
    method = stub.SetSessionHoisted  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "SetSessionHoistedReply",
        await method(SetSessionHoistedRequest(session_id=session_id, hoisted=hoisted)),
    )


async def _serve(
    store: SessionStore, *, cascade: SessionMemoryCascade | None = None
) -> tuple[aio.Server, str]:
    """A BrainService over `store` (and an optional delete cascade) on a loopback port."""
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    server, port = create_server(
        RpcServerConfig(host="127.0.0.1", port=0),
        lambda _confirmer, _progress: engine,
        store,
        RpcPorts(memory_cascade=cascade),
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
    assert all(not s.hoisted for s in reply.sessions)


async def test_list_sessions_zero_limit_uses_the_server_default() -> None:
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
    assert [s.session_id for s in reply.sessions] == ["beta"]


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
    """A SessionStore whose reads and its rename, delete and `set_hoisted` writes raise."""

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
        msg = "redis is down"
        raise SessionStoreError(msg)

    async def delete(self, session_id: str) -> None:
        del session_id
        msg = "redis is down"
        raise SessionStoreError(msg)

    async def set_hoisted(self, session_id: str, *, hoisted: bool) -> None:
        del session_id, hoisted
        msg = "redis is down"
        raise SessionStoreError(msg)

    async def set_recap(self, session_id: str, recap: HistoryRecap) -> None:
        del session_id, recap
        msg = "redis is down"
        raise SessionStoreError(msg)

    async def recap(self, session_id: str) -> HistoryRecap | None:
        del session_id
        msg = "redis is down"
        raise SessionStoreError(msg)


class FailingMemoryStore:
    """A MemoryStore whose delete_scope raises, to drive DeleteSession's MemoryStoreError abort."""

    async def add(self, record: MemoryRecord) -> None:
        del record

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        del embedding, k, scopes
        return ()

    async def count_candidates(self, *, scopes: Sequence[str] | None = None) -> int:
        del scopes
        return 0

    async def delete_scope(self, scope: str) -> int:
        del scope
        msg = "pgvector is down"
        raise MemoryStoreError(msg)


class UndecodableMemoryStore(FailingMemoryStore):
    """A MemoryStore whose delete_scope answers with a reply this repo cannot read."""

    async def delete_scope(self, scope: str) -> int:
        del scope
        msg = "malformed delete status from the memory store"
        raise MemoryDataError(msg)


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


async def test_rename_session_sets_a_title_visible_in_the_listing() -> None:
    store = await _seeded_store()
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            await _rename(stub, "alpha", "Everything about cats")
            reply = await _list(stub, limit=0)
    finally:
        await server.stop(grace=None)
    alpha = next(s for s in reply.sessions if s.session_id == "alpha")
    assert alpha.title == "Everything about cats"
    assert alpha.preview == "cats are great"


async def test_rename_session_with_empty_title_restores_the_derivation() -> None:
    store = await _seeded_store()
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            await _rename(stub, "alpha", "A custom label")
            await _rename(stub, "alpha", "")
            reply = await _list(stub, limit=0)
    finally:
        await server.stop(grace=None)
    alpha = next(s for s in reply.sessions if s.session_id == "alpha")
    assert alpha.title == "about cats"


async def test_rename_session_store_failure_aborts_unavailable() -> None:
    server, address = await _serve(FailingStore())
    try:
        async with aio.insecure_channel(address) as channel:
            with pytest.raises(aio.AioRpcError) as excinfo:
                await _rename(BrainServiceStub(channel), "alpha", "new title")
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() is grpc.StatusCode.UNAVAILABLE
    assert "redis is down" in (excinfo.value.details() or "")


async def test_delete_session_removes_a_chat_from_the_listing_and_history() -> None:
    store = await _seeded_store()
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            await _delete(stub, "alpha")
            listed = await _list(stub, limit=0)
            gone = await _messages(stub, "alpha")
    finally:
        await server.stop(grace=None)
    assert [s.session_id for s in listed.sessions] == ["beta"]
    assert list(gone.messages) == []


async def test_delete_session_cascades_to_session_scoped_memories_but_spares_global() -> None:
    store = await _seeded_store()
    mem = InMemoryMemoryStore()
    await mem.add(
        MemoryRecord(id="a1", text="alpha secret", embedding=(1.0,), at=_T0, scope="alpha")
    )
    await mem.add(
        MemoryRecord(id="g1", text="shared fact", embedding=(1.0,), at=_T0, scope="global")
    )
    cascade = SessionMemoryCascade(mem, SessionMemoryScope())
    server, address = await _serve(store, cascade=cascade)
    try:
        async with aio.insecure_channel(address) as channel:
            await _delete(BrainServiceStub(channel), "alpha")
    finally:
        await server.stop(grace=None)
    assert list(await mem.search((1.0,), k=5, scopes=["alpha"])) == []
    survived = await mem.search((1.0,), k=5, scopes=["global"])
    assert [hit.record.id for hit in survived] == ["g1"]


async def test_delete_session_store_failure_aborts_unavailable() -> None:
    server, address = await _serve(FailingStore())
    try:
        async with aio.insecure_channel(address) as channel:
            with pytest.raises(aio.AioRpcError) as excinfo:
                await _delete(BrainServiceStub(channel), "alpha")
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() is grpc.StatusCode.UNAVAILABLE
    assert "redis is down" in (excinfo.value.details() or "")


async def test_set_session_hoisted_lifts_an_old_chat_above_the_recency_window() -> None:
    store = await _seeded_store()
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            before = await _list(stub, limit=1)
            await _set_hoisted(stub, "alpha", hoisted=True)
            hoisted_listing = await _list(stub, limit=1)
            await _set_hoisted(stub, "alpha", hoisted=False)
            after = await _list(stub, limit=1)
    finally:
        await server.stop(grace=None)
    assert [s.session_id for s in before.sessions] == ["beta"]
    ids = [s.session_id for s in hoisted_listing.sessions]
    assert ids == ["alpha", "beta"]
    assert hoisted_listing.sessions[0].hoisted is True
    assert hoisted_listing.sessions[1].hoisted is False
    assert [s.session_id for s in after.sessions] == ["beta"]


async def test_set_session_hoisted_store_failure_aborts_unavailable() -> None:
    server, address = await _serve(FailingStore())
    try:
        async with aio.insecure_channel(address) as channel:
            with pytest.raises(aio.AioRpcError) as excinfo:
                await _set_hoisted(BrainServiceStub(channel), "alpha", hoisted=True)
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() is grpc.StatusCode.UNAVAILABLE
    assert "redis is down" in (excinfo.value.details() or "")


async def test_delete_session_memory_cascade_failure_aborts_unavailable() -> None:
    store = await _seeded_store()
    cascade = SessionMemoryCascade(FailingMemoryStore(), SessionMemoryScope())
    server, address = await _serve(store, cascade=cascade)
    try:
        async with aio.insecure_channel(address) as channel:
            with pytest.raises(aio.AioRpcError) as excinfo:
                await _delete(BrainServiceStub(channel), "alpha")
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() is grpc.StatusCode.UNAVAILABLE
    assert "pgvector is down" in (excinfo.value.details() or "")


async def test_delete_session_undecodable_memory_reply_aborts_internal() -> None:
    store = await _seeded_store()
    cascade = SessionMemoryCascade(UndecodableMemoryStore(), SessionMemoryScope())
    server, address = await _serve(store, cascade=cascade)
    try:
        async with aio.insecure_channel(address) as channel:
            with pytest.raises(aio.AioRpcError) as excinfo:
                await _delete(BrainServiceStub(channel), "alpha")
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() is grpc.StatusCode.INTERNAL
    assert "malformed delete status" in (excinfo.value.details() or "")
    assert [s.session_id for s in await store.list_sessions(limit=10)] == ["beta"]
