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
    SeamPorts,
    SeamServerConfig,
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
    SetSessionPinnedReply,
    SetSessionPinnedRequest,
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


async def _rename(stub: BrainServiceStub, session_id: str, title: str) -> RenameSessionReply:
    method = stub.RenameSession  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "RenameSessionReply",
        await method(RenameSessionRequest(session_id=session_id, title=title)),
    )


async def _delete(stub: BrainServiceStub, session_id: str) -> DeleteSessionReply:
    method = stub.DeleteSession  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("DeleteSessionReply", await method(DeleteSessionRequest(session_id=session_id)))


async def _set_pinned(
    stub: BrainServiceStub, session_id: str, *, pinned: bool
) -> SetSessionPinnedReply:
    method = stub.SetSessionPinned  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(
        "SetSessionPinnedReply",
        await method(SetSessionPinnedRequest(session_id=session_id, pinned=pinned)),
    )


async def _serve(
    store: SessionStore, *, cascade: SessionMemoryCascade | None = None
) -> tuple[aio.Server, str]:
    """A BrainService over `store` (and an optional delete cascade) on a loopback port."""
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    server, port = create_server(
        SeamServerConfig(host="127.0.0.1", port=0),
        lambda _confirmer, _progress: engine,
        store,
        SeamPorts(memory_cascade=cascade),
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
    assert all(not s.pinned for s in reply.sessions)  # nothing pinned by default


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
    """A SessionStore whose reads and the rename/delete/pin writes raise, to drive the handlers'
    UNAVAILABLE abort paths (ADR-0021)."""

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

    async def set_pinned(self, session_id: str, *, pinned: bool) -> None:
        del session_id, pinned
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
    """A MemoryStore whose delete_scope raises, to drive DeleteSession's MemoryStoreError abort.

    Wrapped in a real `SessionMemoryCascade` under session scoping so the cascade genuinely calls
    `delete_scope` (rather than short-circuiting) and its failure crosses the port.
    """

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
    """A MemoryStore whose delete_scope answers with a reply this repo cannot read.

    The other half of the same port: the real adapter raises this when Postgres returns a `DELETE`
    command tag it cannot parse a count out of, which is the store answering rather than the store
    being unreachable. Wrapped in the same real cascade, so the id it fails on is the seam's.
    """

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
    # The user-driven rename write: the switcher shows the chosen label, not the derivation.
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
    assert alpha.preview == "cats are great"  # the preview still derives from the last message


async def test_rename_session_with_empty_title_restores_the_derivation() -> None:
    # "" clears the override, so the switcher falls back to the first-message title.
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
    assert alpha.title == "about cats"  # the first-message derivation is back


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
    # The destructive management write over the seam: after delete, the chat is gone from the
    # switcher's listing and its history reads empty, while a sibling chat is untouched.
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
    assert [s.session_id for s in listed.sessions] == ["beta"]  # alpha dropped, beta kept
    assert list(gone.messages) == []  # its transcript is gone (the unknown-session behavior)


async def test_delete_session_cascades_to_session_scoped_memories_but_spares_global() -> None:
    # End-to-end cascade under session scoping: deleting a chat forgets its own-scope memories,
    # while a global-scope memory (the shared cross-conversation space) is never swept.
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
    assert list(await mem.search((1.0,), k=5, scopes=["alpha"])) == []  # alpha's memory forgotten
    survived = await mem.search((1.0,), k=5, scopes=["global"])  # the shared space is intact
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


async def test_set_session_pinned_lifts_an_old_chat_above_the_recency_window() -> None:
    # The whole point of pinning over the seam: 'alpha' is the OLDER chat, so a limit=1 window holds
    # only 'beta'. Pinning 'alpha' unions it back into the listing, ABOVE the recency group, with
    # its wire `pinned` flag set. Unpinning drops it back out. This test fails if the servicer does
    # not forward the pin, or if `list_sessions` stops unioning the pinned set.
    store = await _seeded_store()
    server, address = await _serve(store)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            before = await _list(stub, limit=1)  # only the newest chat fits the window
            await _set_pinned(stub, "alpha", pinned=True)
            pinned_listing = await _list(stub, limit=1)
            await _set_pinned(stub, "alpha", pinned=False)
            after = await _list(stub, limit=1)
    finally:
        await server.stop(grace=None)
    assert [s.session_id for s in before.sessions] == ["beta"]  # alpha is outside the window
    ids = [s.session_id for s in pinned_listing.sessions]
    assert ids == ["alpha", "beta"]  # the pin lifts alpha in, above the recency group
    assert pinned_listing.sessions[0].pinned is True
    assert pinned_listing.sessions[1].pinned is False
    assert [s.session_id for s in after.sessions] == ["beta"]  # unpinning drops it back out


async def test_set_session_pinned_store_failure_aborts_unavailable() -> None:
    server, address = await _serve(FailingStore())
    try:
        async with aio.insecure_channel(address) as channel:
            with pytest.raises(aio.AioRpcError) as excinfo:
                await _set_pinned(BrainServiceStub(channel), "alpha", pinned=True)
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() is grpc.StatusCode.UNAVAILABLE
    assert "redis is down" in (excinfo.value.details() or "")


async def test_delete_session_memory_cascade_failure_aborts_unavailable() -> None:
    # The session delete succeeds, then the cascade raises MemoryStoreError; the handler surfaces it
    # as UNAVAILABLE. The operation is idempotent, so a retry re-runs the cascade and finishes it.
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
    """The cascade's data defect is a fault of this side, so it is not reported as an outage.

    The two failures reach this handler through one port and one call, and the difference is
    whether the condition passes on its own: an unreachable Postgres comes back, while a reply
    nothing here can decode reads the same on every later attempt. `UNAVAILABLE` is the seam's
    word for the first, and using it for the second sends whoever reads the code, an operator
    included, looking for an outage that is not there.

    What is deliberately NOT claimed is a change of behaviour: the body classifies this method as
    non-repeatable and retries only `Unavailable` anyway, so nothing on either side ever repeated
    it. This is the label, and the same distinction the turn path already draws.
    """
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
    # The chat itself is gone: the cascade runs second, so the user's primary intent stands and
    # a retry re-runs only the forget.
    assert [s.session_id for s in await store.list_sessions(limit=10)] == ["beta"]
