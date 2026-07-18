"""GrpcBodyGateway: the BodyGateway port over the body's BodyService gRPC seam (ADR-0023)."""

from collections.abc import Awaitable, Callable
from typing import cast

from grpc import aio

from cortex_core import (
    BodyGatewayError,
    ImageError,
    ImagePart,
    ScreenCapture,
    VolumeState,
    captured_at_from_unix_ms,
)
from cortex_seam import (
    SEAM_TOKEN_HEADER,
    BodyServiceStub,
    CaptureScreenReply,
    CaptureScreenRequest,
    GetVolumeRequest,
    NotifyReply,
    NotifyRequest,
    SetVolumeRequest,
)
from cortex_seam import VolumeState as VolumeStatePb

_Metadata = tuple[tuple[str, str], ...]

MAX_RECEIVE_BYTES = 16 * 1024 * 1024


class GrpcBodyGateway:
    """BodyGateway over a ``BodyService`` gRPC channel (the ``LlamaCppBackend`` of OS actions)."""

    def __init__(
        self, channel: aio.Channel, *, token: str = "", capture_timeout_s: float = 10.0
    ) -> None:
        self._stub = BodyServiceStub(channel)
        self._capture_timeout_s = capture_timeout_s
        # Attach the token on every call when configured; empty token = no metadata, matching
        # the tokenless body server (ADR-0016). Built once because the metadata never changes.
        self._metadata: _Metadata = ((SEAM_TOKEN_HEADER, token),) if token else ()

    @classmethod
    async def connect(
        cls, endpoint: str, *, token: str = "", capture_timeout_s: float = 10.0
    ) -> tuple["GrpcBodyGateway", Callable[[], Awaitable[None]]]:
        """Open an insecure channel to the body at ``endpoint`` (e.g. ``host:50151``)."""
        channel = aio.insecure_channel(
            endpoint, options=[("grpc.max_receive_message_length", MAX_RECEIVE_BYTES)]
        )

        async def close() -> None:
            await channel.close()

        return cls(channel, token=token, capture_timeout_s=capture_timeout_s), close

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

    async def capture_screen(self, *, max_edge: int = 0, max_bytes: int = 0) -> ScreenCapture:
        """Read the host's primary display over ``BodyService.CaptureScreen`` (ADR-0029)."""
        request = CaptureScreenRequest(max_edge=max_edge, max_bytes=max_bytes)
        method = self._stub.CaptureScreen  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast(
                "CaptureScreenReply",
                await method(request, metadata=self._metadata, timeout=self._capture_timeout_s),
            )
        except aio.AioRpcError as err:
            msg = f"body capture_screen failed: {err.details()}"
            raise BodyGatewayError(msg) from err
        return _to_capture(reply)


def _to_capture(reply: CaptureScreenReply) -> ScreenCapture:
    """Translate the wire reply into the domain value, refusing anything it will not vouch for."""
    if not reply.HasField("image"):
        msg = "body capture_screen returned no image"
        raise BodyGatewayError(msg)
    blob = reply.image
    try:
        image = ImagePart(
            data=blob.data,
            mime_type=blob.mime_type,
            width=blob.width,
            height=blob.height,
        )
    except ImageError as err:
        msg = f"body capture_screen returned an unusable image: {err}"
        raise BodyGatewayError(msg) from err
    return ScreenCapture(
        image=image,
        source_width=blob.source_width or blob.width,
        source_height=blob.source_height or blob.height,
        captured_at=captured_at_from_unix_ms(blob.captured_at_unix_ms),
    )
