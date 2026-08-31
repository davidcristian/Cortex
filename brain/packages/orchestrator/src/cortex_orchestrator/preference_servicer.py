"""Preference servicer methods: the wire-binding half of the user's settings record.

Its own mixin beside ``session_servicer`` (the same line-cap split), holding the two preference
RPCs ``BrainService`` mixes in. Each is a thin binding onto the ``PreferenceStore``: no policy, no
interpretation of a value, and ``UNAVAILABLE`` on a store failure (the read-path precedent).

With no store wired both answer benignly rather than erroring, following the ``ScheduleStore``
precedent: a brain with no preference record is indistinguishable from one whose record is empty,
and a body that cannot persist a choice should still apply it for the session.
"""

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
    """The preference RPCs, mixed into ``BrainService``.

    Reads the ``BrainService``-injected optional preference store (`_preferences`), declared as a
    required attribute so any host class must provide it (as `None` when the capability is off).
    """

    _preferences: PreferenceStore | None

    async def GetPreferences(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: GetPreferencesRequest,
        context: aio.ServicerContext[GetPreferencesRequest, GetPreferencesReply],
    ) -> GetPreferencesReply:
        """Every stored pair; empty with no store wired, and a store failure aborts."""
        del request  # the generated servicer signature; this RPC takes no arguments
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
