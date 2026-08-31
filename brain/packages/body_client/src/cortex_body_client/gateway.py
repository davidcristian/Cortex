"""GrpcBodyGateway: the BodyGateway port over the body's BodyService gRPC seam (ADR-0023).

A thin gRPC client wrapping ``cortex_seam.BodyServiceStub`` over an injected ``grpc.aio.Channel``.
It translates the domain ``VolumeState`` to and from the wire message, builds ``SetVolumeRequest``
with proto explicit presence (a ``None`` field is left unset, so the body sets level, mute, or
both), attaches the shared seam token as ``x-cortex-seam-token`` metadata (ADR-0016, mirrored for
this direction), and maps every gRPC failure to ``BodyGatewayError`` with the cause chained and
the status classified into a ``BodyFailure`` kind (``failures.py``), which is how the core can
word a refusal as a refusal rather than as an unreachable body. No orchestration, no state: the
composition root owns the channel's lifecycle, and ``connect`` returns the closer.

Every call on this seam carries a deadline, and ``capture_screen`` is attempted once and never
retried. docs/modules/brain-body-client.md argues both, including why the two deadlines differ
(ADR-0029 uniform-deadline addendum).

The generated gRPC stub ships no ``.pyi`` (wire code is gate-exempt, ADR-0002 d4), so the
stub-method accesses carry the same narrow, justified ignores the seam's other consumers use.
"""

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

# The two ends of the capture vocabulary, written out pair by pair rather than derived from either
# side's ordering. A positional coincidence (both zeroes meaning "the whole display") is not a
# coupling a reader can check, and this is the one place the domain enum and the wire enum meet.
#
# Only the request direction needs a total map. The reply direction reads the wire value back
# through the same pairs and falls to DISPLAY for anything else, which is proto3's rule for an
# unrecognized enum value.
_TARGET_TO_WIRE: dict[CaptureTarget, CaptureTargetPb] = {
    CaptureTarget.DISPLAY: CaptureTargetPb.CAPTURE_TARGET_DISPLAY,
    CaptureTarget.FOCUS: CaptureTargetPb.CAPTURE_TARGET_FOCUS,
}
_TARGET_FROM_WIRE: dict[int, CaptureTarget] = {
    int(wire): target for target, wire in _TARGET_TO_WIRE.items()
}

# The most bytes one inbound gRPC message may carry on this channel, 16 MiB.
#
# grpc's own default is 4 MiB, which a legitimate capture can exceed: the body's ceiling is
# 6 MiB and a worst-case incompressible screen encodes to 4.33 MB at the default edge. The
# limit sits well above both ceilings rather than at one of them, so a reply that breaks the
# domain budget fails the domain check, with a message the cortex can read, instead of being
# killed by the transport with a message nobody can act on. Only this direction is raised;
# nothing else on this seam carries a payload.
MAX_RECEIVE_BYTES = 16 * 1024 * 1024

# How long a screen capture may take before the adapter stops waiting, in seconds. Generous,
# because the work really is a blit plus a downscale plus an encode of a 4K desktop.
DEFAULT_CAPTURE_TIMEOUT_S = 10.0

# How long every other call on this seam may take. Half the capture's, because a volume read and a
# toast are host calls with no work in them: five seconds is far past a healthy one and short
# enough that a wedged endpoint fails a tool instead of a turn.
#
# Declared here rather than in the orchestrator's settings because this is the adapter that spends
# it, and a default spelled in both places is two numbers that only look like one (``config_body``
# imports these, the way ``config.py`` takes its Redis URL from the session adapter).
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
        # Attach the token on every call when configured; empty token = no metadata, matching
        # the tokenless body server (ADR-0016). Built once because the metadata never changes.
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
        """Open an insecure channel to the body at ``endpoint`` (e.g. ``host:50151``).

        Returns the adapter and the coroutine that closes its channel, so the composition
        root's shutdown path is uniform with the other builders. The channel connects lazily, so
        an unreachable body surfaces as ``BodyGatewayError`` on the first call, not here, and
        it surfaces within ``call_timeout_s`` rather than after grpc's own connect backoff.
        """
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
        """Apply a volume change over ``BodyService.SetVolume`` and report the resulting state.

        ``level``/``mute`` ride as proto optional fields (``None`` leaves a field unset), so the
        request carries exactly what the caller set. The body clamps and applies it. Attempted
        once, bounded by ``call_timeout_s``, and never retried: a repeated write is a second host
        action for one user intent.
        """
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
        """Show a native notification over ``BodyService.Notify`` (ADR-0025).

        Returns the body's ``shown`` verdict, where ``False`` means the host was reached
        and declined (notifications switched off). Every gRPC failure, including the
        ``Unimplemented`` a body predating the toast answers, becomes a
        ``BodyGatewayError``. The ticker treats a declined and a failed push alike: the
        reminder stays deliverable for the pull path.

        ``call_timeout_s`` bounds it. The ticker already bounds the whole fire against the
        reminder's lease, so this deadline does not save the ticker from hanging; it stops one
        wedged toast from spending a lease that covers the store writes after it.
        """
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
        """Read the host's screen over ``BodyService.CaptureScreen`` (ADR-0029).

        ``max_edge``/``max_bytes`` are hints on the wire and bounds on the reply: a zero asks for
        the body's own default and holds the reply to the domain constants only, and a non-zero
        value is re-verified here on receipt. Under proto3 an older body ignores both without
        reporting anything and answers full resolution, so a request hint is an optimization and
        never a guarantee; ``ImagePart``'s own checks are the domain ceiling and cannot enforce a
        number this deployment chose.

        ``target`` is the third thing the wire cannot guarantee, and the one the caller cannot
        re-verify from the pixels, since a crop and a shrunk screen are the same blob. The reply
        carries what the body pointed at, and that is what the returned value reports, never the
        ask. An old body that sets nothing reads as ``DISPLAY``, which is all such a body can do.

        Attempted exactly once, bounded by ``capture_timeout_s``. Every failure, including a bound
        the wire cannot carry and a reply outside the bounds asked for, becomes
        ``BodyGatewayError``, which the tool turns into a recoverable result rather than an
        exception.
        """
        try:
            request = CaptureScreenRequest(
                max_edge=max_edge, max_bytes=max_bytes, target=_TARGET_TO_WIRE[target]
            )
        except ValueError as err:
            # A misconfigured bound must not escape as a bare ValueError: BodyGatewayError is this
            # port's only failure channel, and anything else kills the turn instead of failing the
            # capture.
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
    """Translate the wire reply into the domain value, raising on anything outside the bounds.

    A body that answers ``CaptureScreenReply()`` with no blob at all answered OK to a capture it
    did not take, which is worse than an error status because the caller would otherwise read
    zeros as a real screen.
    """
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
