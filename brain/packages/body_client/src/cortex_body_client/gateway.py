"""GrpcBodyGateway: the BodyGateway port over the body's BodyService gRPC interface."""

from collections.abc import Awaitable, Callable
from typing import cast

from grpc import aio

from cortex_body_client.failures import kind_of
from cortex_core import (
    BodyGatewayError,
    CaptureTarget,
    ImageError,
    ImagePart,
    ScreenCapture,
    VolumeState,
    captured_at_from_unix_ms,
    hold_to_the_bounds_asked_for,
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
from cortex_seam import CaptureTarget as CaptureTargetPb
from cortex_seam import VolumeState as VolumeStatePb

_Metadata = tuple[tuple[str, str], ...]

# Written out pair by pair rather than derived from either side's ordering: a positional
# coincidence is not something a reader can check. The reply direction reads the wire value back
# through the same pairs and falls to DISPLAY for anything else, which is proto3's rule.
_TARGET_TO_WIRE: dict[CaptureTarget, CaptureTargetPb] = {
    CaptureTarget.DISPLAY: CaptureTargetPb.CAPTURE_TARGET_DISPLAY,
    CaptureTarget.FOCUS: CaptureTargetPb.CAPTURE_TARGET_FOCUS,
}
_TARGET_FROM_WIRE: dict[int, CaptureTarget] = {
    int(wire): target for target, wire in _TARGET_TO_WIRE.items()
}

# grpc's own default is 4 MiB, which a legitimate capture can exceed: the body's ceiling is
# 6 MiB and a worst-case incompressible screen encodes to 4.33 MB at the default edge. The limit
# sits above both, so an oversized reply fails the domain check rather than the transport.
MAX_RECEIVE_BYTES = 16 * 1024 * 1024

# Generous, because a capture really is a blit plus a downscale plus an encode of a 4K desktop.
DEFAULT_CAPTURE_TIMEOUT_S = 10.0

# Every other call on this interface. Half the capture's, because a volume read and a toast are
# host calls with no work in them. Declared here rather than in the orchestrator settings
# because this is the adapter that spends it, and `config_body` imports it from here.
DEFAULT_CALL_TIMEOUT_S = 5.0


class GrpcBodyGateway:
    """BodyGateway over a ``BodyService`` gRPC channel."""

    def __init__(
        self,
        channel: aio.Channel,
        *,
        token: str = "",
        capture_timeout_s: float = DEFAULT_CAPTURE_TIMEOUT_S,
        call_timeout_s: float = DEFAULT_CALL_TIMEOUT_S,
    ) -> None:
        self._stub = BodyServiceStub(channel)
        self._capture_timeout_s = capture_timeout_s
        self._call_timeout_s = call_timeout_s
        # An empty token means no metadata, which is what a tokenless body server expects.
        self._metadata: _Metadata = ((SEAM_TOKEN_HEADER, token),) if token else ()

    @classmethod
    async def connect(
        cls,
        endpoint: str,
        *,
        token: str = "",
        capture_timeout_s: float = DEFAULT_CAPTURE_TIMEOUT_S,
        call_timeout_s: float = DEFAULT_CALL_TIMEOUT_S,
    ) -> tuple["GrpcBodyGateway", Callable[[], Awaitable[None]]]:
        """Open an insecure channel to the body at ``endpoint`` (e.g. ``host:50151``)."""
        channel = aio.insecure_channel(
            endpoint, options=[("grpc.max_receive_message_length", MAX_RECEIVE_BYTES)]
        )

        async def close() -> None:
            await channel.close()

        gateway = cls(
            channel,
            token=token,
            capture_timeout_s=capture_timeout_s,
            call_timeout_s=call_timeout_s,
        )
        return gateway, close

    async def get_volume(self) -> VolumeState:
        """Read the host volume over ``BodyService.GetVolume``, bounded by ``call_timeout_s``."""
        method = self._stub.GetVolume  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast(
                "VolumeStatePb",
                await method(
                    GetVolumeRequest(), metadata=self._metadata, timeout=self._call_timeout_s
                ),
            )
        except aio.AioRpcError as err:
            msg = f"body get_volume failed: {err.details()}"
            raise BodyGatewayError(msg, kind=kind_of(err)) from err
        return VolumeState(level=reply.level, muted=reply.muted)

    async def set_volume(
        self, *, level: float | None = None, mute: bool | None = None
    ) -> VolumeState:
        """Apply a volume change over ``BodyService.SetVolume`` and report the resulting state."""
        request = SetVolumeRequest(level=level, mute=mute)
        method = self._stub.SetVolume  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast(
                "VolumeStatePb",
                await method(request, metadata=self._metadata, timeout=self._call_timeout_s),
            )
        except aio.AioRpcError as err:
            msg = f"body set_volume failed: {err.details()}"
            raise BodyGatewayError(msg, kind=kind_of(err)) from err
        return VolumeState(level=reply.level, muted=reply.muted)

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool:
        """Show a native notification over ``BodyService.Notify``."""
        request = NotifyRequest(title=title, body=body, reminder_id=reminder_id, tainted=tainted)
        method = self._stub.Notify  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast(
                "NotifyReply",
                await method(request, metadata=self._metadata, timeout=self._call_timeout_s),
            )
        except aio.AioRpcError as err:
            msg = f"body notify failed: {err.details()}"
            raise BodyGatewayError(msg, kind=kind_of(err)) from err
        return reply.shown

    async def capture_screen(
        self,
        *,
        max_edge: int = 0,
        max_bytes: int = 0,
        target: CaptureTarget = CaptureTarget.DISPLAY,
    ) -> ScreenCapture:
        """Read the host's screen over ``BodyService.CaptureScreen``."""
        try:
            request = CaptureScreenRequest(
                max_edge=max_edge, max_bytes=max_bytes, target=_TARGET_TO_WIRE[target]
            )
        except ValueError as err:
            # A misconfigured bound must not escape as a bare ValueError: this port's only
            # failure channel is BodyGatewayError, and anything else kills the turn.
            msg = f"body capture_screen was asked for a bound the wire cannot hold: {err}"
            raise BodyGatewayError(msg) from err
        method = self._stub.CaptureScreen  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast(
                "CaptureScreenReply",
                await method(request, metadata=self._metadata, timeout=self._capture_timeout_s),
            )
        except aio.AioRpcError as err:
            msg = f"body capture_screen failed: {err.details()}"
            raise BodyGatewayError(msg, kind=kind_of(err)) from err
        return _to_capture(reply, max_edge=max_edge, max_bytes=max_bytes)


def _to_capture(reply: CaptureScreenReply, *, max_edge: int, max_bytes: int) -> ScreenCapture:
    """Translate the wire reply into the domain value, raising on anything outside the bounds."""
    if not reply.HasField("image"):
        msg = "body capture_screen returned no image"
        raise BodyGatewayError(msg)
    blob = reply.image
    hold_to_the_bounds_asked_for(
        width=blob.width,
        height=blob.height,
        byte_count=len(blob.data),
        max_edge=max_edge,
        max_bytes=max_bytes,
    )
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
        target=_TARGET_FROM_WIRE.get(reply.resolved_target, CaptureTarget.DISPLAY),
    )
