"""Session-catalog servicer methods (ADR-0021): the wire-binding half of the session RPCs.

Split from ``server.py`` for the line cap: ``SessionRpcMixin`` holds the five session-management
servicer methods (list, history, rename, delete, pin) that ``BrainService`` mixes in, so the
servicer shell stays thin (the ``session_rpc.py`` / ``reminders.py`` precedent). Each method is a
thin binding onto the session store: it delegates the mapping and the gated writes to
``session_rpc`` and aborts ``UNAVAILABLE`` on a store failure (the read-path precedent), with
``DeleteSession`` naming ``INTERNAL`` as well for the one narrower failure its cascade can meet.
The mixin reads the same injected ``SessionStore`` (and, for delete, the optional
``SessionMemoryCascade``) that ``BrainService`` constructs; it holds no state of its own.
"""

import grpc
from grpc import aio

from cortex_core import (
    MemoryDataError,
    MemoryStoreError,
    SessionMemoryCascade,
    SessionStore,
    SessionStoreError,
)
from cortex_orchestrator.session_rpc import (
    clamp_limit,
    delete_session,
    message_to_proto,
    rename_session,
    set_session_pinned,
    summary_to_proto,
)
from cortex_seam import (
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


class SessionRpcMixin:
    """The session-catalog RPCs, mixed into ``BrainService`` (ADR-0021).

    Reads the ``BrainService``-injected session store (`_store`) and, for delete, the optional
    memory cascade (`_memory_cascade`); both are declared as required attributes so any host class
    must provide them. Every method delegates to ``session_rpc`` and aborts ``UNAVAILABLE`` on a
    store failure, the session-read precedent; ``DeleteSession`` additionally aborts ``INTERNAL``
    on the memory port's narrower data defect, which is the one failure here that never heals.
    """

    _store: SessionStore
    _memory_cascade: SessionMemoryCascade | None

    async def ListSessions(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: ListSessionsRequest,
        context: aio.ServicerContext[ListSessionsRequest, ListSessionsReply],
    ) -> ListSessionsReply:
        """Recent chats newest-first, pinned unioned in (ADR-0021); store error aborts."""
        try:
            summaries = await self._store.list_sessions(limit=clamp_limit(request.limit))
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
        return ListSessionsReply(sessions=[summary_to_proto(s) for s in summaries])

    async def GetSessionMessages(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: GetSessionMessagesRequest,
        context: aio.ServicerContext[GetSessionMessagesRequest, GetSessionMessagesReply],
    ) -> GetSessionMessagesReply:
        """One session's history in append order (ADR-0021); unknown is empty, error aborts."""
        try:
            messages = await self._store.history(request.session_id)
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
        return GetSessionMessagesReply(messages=[message_to_proto(m) for m in messages])

    async def RenameSession(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: RenameSessionRequest,
        context: aio.ServicerContext[RenameSessionRequest, RenameSessionReply],
    ) -> RenameSessionReply:
        """Gated user-only rename via `session_rpc.rename_session` (ADR-0021); error aborts."""
        try:
            return await rename_session(self._store, request.session_id, request.title)
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))

    async def DeleteSession(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: DeleteSessionRequest,
        context: aio.ServicerContext[DeleteSessionRequest, DeleteSessionReply],
    ) -> DeleteSessionReply:
        """Gated user-only delete + memory cascade via `session_rpc.delete_session` (ADR-0021).

        The one method here whose port declares a narrower failure, so it is the one that names
        two codes. A cascade whose `delete_scope` met a reply this repo cannot read raises
        `MemoryDataError`, and that is not an outage: the row or the schema is wrong, so it reads
        the same on the next attempt and the next week, where every other `MemoryStoreError` says
        Postgres was unreachable and heals by itself. `UNAVAILABLE` is the seam's word for the
        second and would be a lie about the first, `INTERNAL` its word for a fault of this side.

        Naming it changes what the failure says and not what either side does with it: the body
        classifies this method as non-repeatable, so no code on it was ever retried, and the
        overlay offers no per-code affordance. It is the same distinction the turn path already
        draws, carried to the third call site on the cascade so all three read alike.
        """
        try:
            return await delete_session(self._store, self._memory_cascade, request.session_id)
        except MemoryDataError as err:
            await context.abort(grpc.StatusCode.INTERNAL, str(err))
        except (SessionStoreError, MemoryStoreError) as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))

    async def SetSessionPinned(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: SetSessionPinnedRequest,
        context: aio.ServicerContext[SetSessionPinnedRequest, SetSessionPinnedReply],
    ) -> SetSessionPinnedReply:
        """Gated user-only pin toggle via `session_rpc.set_session_pinned` (ADR-0021 pinning)."""
        try:
            return await set_session_pinned(self._store, request.session_id, pinned=request.pinned)
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
