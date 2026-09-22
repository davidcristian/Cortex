"""Session-catalog servicer methods: the wire-binding half of the session RPCs."""

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
    set_session_hoisted,
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
    SetSessionHoistedReply,
    SetSessionHoistedRequest,
)


class SessionRpcMixin:
    """The session-catalog RPCs, mixed into ``BrainService``."""

    _store: SessionStore
    _memory_cascade: SessionMemoryCascade | None

    async def ListSessions(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: ListSessionsRequest,
        context: aio.ServicerContext[ListSessionsRequest, ListSessionsReply],
    ) -> ListSessionsReply:
        """Recent chats newest first, with the hoisted ones unioned in; a store error aborts."""
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
        """One session's history in append order; unknown is empty, error aborts."""
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
        """User-only rename via `session_rpc.rename_session`; a store error aborts."""
        try:
            return await rename_session(self._store, request.session_id, request.title)
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))

    async def DeleteSession(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: DeleteSessionRequest,
        context: aio.ServicerContext[DeleteSessionRequest, DeleteSessionReply],
    ) -> DeleteSessionReply:
        """User-only delete plus memory cascade via `session_rpc.delete_session`."""
        try:
            return await delete_session(self._store, self._memory_cascade, request.session_id)
        except MemoryDataError as err:
            await context.abort(grpc.StatusCode.INTERNAL, str(err))
        except (SessionStoreError, MemoryStoreError) as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))

    async def SetSessionHoisted(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: SetSessionHoistedRequest,
        context: aio.ServicerContext[SetSessionHoistedRequest, SetSessionHoistedReply],
    ) -> SetSessionHoistedReply:
        """User-only hoist toggle via `session_rpc.set_session_hoisted`."""
        try:
            return await set_session_hoisted(
                self._store, request.session_id, hoisted=request.hoisted
            )
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
