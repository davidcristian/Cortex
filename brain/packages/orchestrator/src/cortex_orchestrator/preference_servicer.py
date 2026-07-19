"""Preference servicer methods: the wire-binding half of the user's settings record."""

import grpc
from grpc import aio

from cortex_core import PreferenceStore, PreferenceStoreError
from cortex_seam import (
    GetPreferencesReply,
    GetPreferencesRequest,
    Preference,
    SetPreferenceReply,
    SetPreferenceRequest,
)


class PreferenceRpcMixin:
    """The preference RPCs, mixed into ``BrainService``."""

    _preferences: PreferenceStore | None

    async def GetPreferences(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: GetPreferencesRequest,
        context: aio.ServicerContext[GetPreferencesRequest, GetPreferencesReply],
    ) -> GetPreferencesReply:
        """Every stored pair; empty with no store wired, and a store failure aborts."""
        del request
        if self._preferences is None:
            return GetPreferencesReply()
        try:
            stored = await self._preferences.all()
        except PreferenceStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
        return GetPreferencesReply(
            preferences=[Preference(key=key, value=value) for key, value in sorted(stored.items())]
        )

    async def SetPreference(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: SetPreferenceRequest,
        context: aio.ServicerContext[SetPreferenceRequest, SetPreferenceReply],
    ) -> SetPreferenceReply:
        """Write one pair (empty value clears it); a no-op with no store, and errors abort."""
        if self._preferences is None:
            return SetPreferenceReply()
        try:
            await self._preferences.set(request.key, request.value)
        except PreferenceStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
        return SetPreferenceReply()
