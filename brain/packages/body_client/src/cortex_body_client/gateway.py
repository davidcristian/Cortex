"""GrpcBodyGateway: the BodyGateway port over the body's BodyService gRPC seam (ADR-0023).

The brain-side half of the first brain→body direction: a thin gRPC client wrapping
``cortex_seam.BodyServiceStub`` over an injected ``grpc.aio.Channel``. It translates the domain
``VolumeState`` to and from the wire message, builds ``SetVolumeRequest`` with proto explicit
presence (a ``None`` field is left unset, so the body sets level, mute, or both), attaches the
shared seam token as ``x-cortex-seam-token`` metadata (ADR-0016, mirrored for this direction),
and maps every gRPC failure (the body unreachable, a non-OK status) to ``BodyGatewayError``
with the cause chained **and the status classified into a ``BodyFailure`` kind**
(``failures.py``), which is how the core can word a refusal as a refusal rather than as an
unreachable body. No orchestration, no state: the composition root owns the channel's
lifecycle (``connect`` returns the closer), exactly as ``LlamaCppBackend`` injects its client.

``capture_screen`` (ADR-0029) is the first call on this seam that carries a **deadline** and the
reason the channel raises its receive limit. It is the first that can genuinely park a thread (a
4K blit plus a downscale plus a PNG encode), and with no deadline a wedged backend hangs the tool
call, which hangs the turn, forever; the volume and notify calls keep their live-validated
no-deadline behaviour, since changing what works is not a change this slice earned. It is also
**never retried**: a repeat photographs a different screen and fires a second host receipt for
one user intent.

The generated gRPC stub ships no ``.pyi`` (wire code is gate-exempt, ADR-0002 d4), so the
stub-method accesses carry the same narrow, justified ignores the seam's other consumers use.
"""

from collections.abc import Awaitable, Callable
from typing import cast

from grpc import aio

from cortex_body_client.failures import kind_of
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
    ImageBlob,
    NotifyReply,
    NotifyRequest,
    SetVolumeRequest,
)
from cortex_seam import VolumeState as VolumeStatePb

_Metadata = tuple[tuple[str, str], ...]

# The most bytes one inbound gRPC message may carry on this channel, 16 MiB.
#
# grpc's own default is 4 MiB, which a legitimate capture can exceed: the body's ceiling is
# 6 MiB and a worst-case incompressible screen encodes to 4.33 MB at the default edge. The
# limit sits well above both ceilings rather than at one of them, so a reply that breaks the
# *domain* budget is refused by the domain, with a message the cortex can read, instead of
# being killed by the transport with a message nobody can act on. Only this direction is
# raised; nothing else on this seam carries a payload.
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
        """Open an insecure channel to the body at ``endpoint`` (e.g. ``host:50151``).

        Returns the adapter and the coroutine that closes its channel, so the composition
        root's shutdown path is uniform with the other builders. The channel connects lazily, so
        an unreachable body surfaces as ``BodyGatewayError`` on the first call, not here.
        """
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
            raise BodyGatewayError(msg, kind=kind_of(err)) from err
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
            raise BodyGatewayError(msg, kind=kind_of(err)) from err
        return VolumeState(level=reply.level, muted=reply.muted)

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool:
        """Show a native notification over ``BodyService.Notify`` (ADR-0025).

        Returns the body's ``shown`` verdict, where ``False`` means the host was reached
        and declined (notifications switched off). Every gRPC failure, including the
        ``Unimplemented`` a body predating the toast answers, becomes a
        ``BodyGatewayError``. The ticker treats a declined and a failed push alike: the
        reminder stays deliverable for the pull path.
        """
        request = NotifyRequest(title=title, body=body, reminder_id=reminder_id, tainted=tainted)
        method = self._stub.Notify  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            reply = cast("NotifyReply", await method(request, metadata=self._metadata))
        except aio.AioRpcError as err:
            msg = f"body notify failed: {err.details()}"
            raise BodyGatewayError(msg, kind=kind_of(err)) from err
        return reply.shown

    async def capture_screen(self, *, max_edge: int = 0, max_bytes: int = 0) -> ScreenCapture:
        """Read the host's primary display over ``BodyService.CaptureScreen`` (ADR-0029).

        ``max_edge``/``max_bytes`` are hints on the wire and **bounds on the reply**: a zero
        asks for the body's own default and holds the reply to the domain constants only, and a
        non-zero value is re-verified here on receipt. That verification is the point. Under
        proto3 an older body silently ignores both and answers full resolution, so a request hint
        is an optimization and never a guarantee; ``ImagePart``'s own checks are the domain
        ceiling and cannot enforce a number this deployment chose.

        Attempted exactly once, with ``timeout`` seconds of patience. Every failure, including a
        bound the wire cannot carry and a reply this side refuses, becomes ``BodyGatewayError``,
        which the tool turns into a recoverable result rather than an exception.
        """
        try:
            request = CaptureScreenRequest(max_edge=max_edge, max_bytes=max_bytes)
        except ValueError as err:
            # A misconfigured bound must not escape as a bare ValueError: this port promises
            # BodyGatewayError as its only failure channel, and anything else kills the turn
            # instead of failing the capture.
            msg = f"body capture_screen was asked for a bound the wire cannot carry: {err}"
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
    """Translate the wire reply into the domain value, refusing anything it will not vouch for.

    A body that answers ``CaptureScreenReply()`` with no blob at all is a body that answered
    OK to a capture it did not take, which is a worse failure than an error status because the
    caller would otherwise read zeros as a real screen.
    """
    if not reply.HasField("image"):
        msg = "body capture_screen returned no image"
        raise BodyGatewayError(msg)
    blob = reply.image
    _hold_to_the_bounds_asked_for(blob, max_edge=max_edge, max_bytes=max_bytes)
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


def _hold_to_the_bounds_asked_for(blob: ImageBlob, *, max_edge: int, max_bytes: int) -> None:
    """Refuse a reply outside the bounds this call asked the body for (ADR-0029 decision 7).

    The receiver verifies after receipt, because a proto3 request field an older body ignores is
    a constraint the brain only believes it set. A zero asked for the body's own default, so
    there is no number to hold it to and only the domain ceiling in ``ImagePart`` applies. The
    body clamps both bounds down to its own, so a reply outside them is a body that did not
    honour the request at all, and the message says which number it broke: a capture that costs
    the turn a megabyte it was told not to spend is not a capture worth having.
    """
    edge = max(blob.width, blob.height)
    if max_edge and edge > max_edge:
        msg = (
            f"body capture_screen answered {blob.width}x{blob.height}, over the {max_edge} px "
            "edge it was asked for"
        )
        raise BodyGatewayError(msg)
    if max_bytes and len(blob.data) > max_bytes:
        msg = (
            f"body capture_screen answered {len(blob.data)} bytes, over the {max_bytes} byte "
            "budget it was asked for"
        )
        raise BodyGatewayError(msg)
