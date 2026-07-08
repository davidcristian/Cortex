"""GrpcBodyGateway: the BodyGateway port over the body's BodyService gRPC seam (ADR-0023)."""

from collections.abc import Awaitable, Callable
from typing import cast

from grpc import aio

from cortex_core import BodyGatewayError, VolumeState
from cortex_seam import (
    SEAM_TOKEN_HEADER,
    BodyServiceStub,
    GetVolumeRequest,
    NotifyReply,
    NotifyRequest,
    SetVolumeRequest,
)
from cortex_seam import VolumeState as VolumeStatePb

_Metadata = tuple[tuple[str, str], ...]


class GrpcBodyGateway:
    """BodyGateway over a ``BodyService`` gRPC channel (the ``LlamaCppBackend`` of OS actions)."""

    def __init__(self, channel: aio.Channel, *, token: str = "") -> None:
        self._stub = BodyServiceStub(channel)
        # Attach the token on every call when configured; empty token = no metadata, matching
        # the tokenless body server (ADR-0016). Built once because the metadata never changes.
        self._metadata: _Metadata = ((SEAM_TOKEN_HEADER, token),) if token else ()

    @classmethod
    async def connect(
        cls, endpoint: str, *, token: str = ""
    ) -> tuple["GrpcBodyGateway", Callable[[], Awaitable[None]]]:
        """Open an insecure channel to the body at ``endpoint`` (e.g. ``host:50151``)."""
        channel = aio.insecure_channel(endpoint)

        async def close() -> None:
            await channel.close()

        return cls(channel, token=token), close

    async def get_volume(self) -> VolumeState:
        """Read the host volume over ``BodyService.GetVolume``."""
        method = self._stub.GetVolume  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast("VolumeStatePb", await method(GetVolumeRequest(), metadata=self._metadata))
        except aio.AioRpcError as err:
            msg = f"body get_volume failed: {err.details()}"
            raise BodyGatewayError(msg) from err
        return VolumeState(level=reply.level, muted=reply.muted)

    async def set_volume(
        self, *, level: float | None = None, mute: bool | None = None
    ) -> VolumeState:
        """Apply a volume change over ``BodyService.SetVolume`` and report the resulting state.

        ``level``/``mute`` ride as proto optional fields (``None`` leaves a field unset), so the
        request carries exactly what the caller set. The body clamps and applies it.
        """
        request = SetVolumeRequest(level=level, mute=mute)
        method = self._stub.SetVolume  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast("VolumeStatePb", await method(request, metadata=self._metadata))
        except aio.AioRpcError as err:
            msg = f"body set_volume failed: {err.details()}"
            raise BodyGatewayError(msg) from err
        return VolumeState(level=reply.level, muted=reply.muted)

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool:
        """Show a native notification over ``BodyService.Notify`` (ADR-0025)."""
        request = NotifyRequest(title=title, body=body, reminder_id=reminder_id, tainted=tainted)
        method = self._stub.Notify  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast("NotifyReply", await method(request, metadata=self._metadata))
        except aio.AioRpcError as err:
            msg = f"body notify failed: {err.details()}"
            raise BodyGatewayError(msg) from err
        return reply.shown
