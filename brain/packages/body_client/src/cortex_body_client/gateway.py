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

**Every call on this seam carries a deadline**, and the two numbers differ because the calls do
(ADR-0029's uniform-deadline addendum). ``capture_screen`` gets the long one: a 4K blit plus a
downscale plus a PNG encode is genuinely slow, and it is the reason the channel raises its
receive limit besides. The volume and notify calls get the short one, because they are fast when
they work at all. What they are not is safe to leave unbounded: the body runs every handler on
``spawn_blocking`` precisely because Core Audio and the toast manager are COM, which has no async
form, and its own ``off_worker`` doc says a COM call can park its thread for as long as the audio
stack or the notification service takes (``body/crates/rpc/src/server.rs``). Nothing above this
adapter bounds a tool call, so an unbounded read of a wedged endpoint hangs the turn forever, and
even a body that is merely absent costs the caller grpc's own connect backoff.

``capture_screen`` is also **never retried**: a repeat photographs a different screen and fires a
second host receipt for one user intent. Bounding is not repeating, though, so the other three are
bounded on their own argument and nothing here retries anything.

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

# The two ends of the capture vocabulary, spelled out rather than derived from either side's
# ordering. A positional coincidence (both zeroes meaning "the whole display") is not a coupling
# a reader can check, and this is the one place the domain enum and the wire enum meet.
#
# Only the request direction needs a total map. The reply direction reads the wire value back
# through the same pairs and falls to DISPLAY for anything else, which is proto3's rule for an
# unrecognized enum and the honest reading besides: a body naming a target this brain does not
# know sent a picture this brain can only describe as the screen it came off.
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
# *domain* budget is refused by the domain, with a message the cortex can read, instead of
# being killed by the transport with a message nobody can act on. Only this direction is
# raised; nothing else on this seam carries a payload.
MAX_RECEIVE_BYTES = 16 * 1024 * 1024

# How long a screen capture may take before the adapter stops waiting, in seconds. Generous,
# because the work really is a blit plus a downscale plus an encode of a 4K desktop, and a
# deadline that fires on a healthy capture is worse than none at all.
DEFAULT_CAPTURE_TIMEOUT_S = 10.0

# How long every other call on this seam may take. Half an order of magnitude under the capture's,
# because a volume read and a toast are host calls with no work in them: five seconds is far past
# a healthy one and short enough that a wedged endpoint fails a tool instead of a turn.
#
# Declared here rather than in the orchestrator's settings because this is the adapter that spends
# it, and a default spelled in both places is two numbers that only look like one (``config_body``
# imports these, the way ``config.py`` takes its Redis URL from the session adapter).
DEFAULT_CALL_TIMEOUT_S = 5.0


class GrpcBodyGateway:
    """BodyGateway over a ``BodyService`` gRPC channel (the ``LlamaCppBackend`` of OS actions)."""

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
        """Read the host volume over ``BodyService.GetVolume``, ``call_timeout_s`` of patience."""
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
        once, with ``call_timeout_s`` of patience, and never retried: a repeated write is a
        second host action for one user intent.
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

        ``max_edge``/``max_bytes`` are hints on the wire and **bounds on the reply**: a zero
        asks for the body's own default and holds the reply to the domain constants only, and a
        non-zero value is re-verified here on receipt. That verification is the point. Under
        proto3 an older body silently ignores both and answers full resolution, so a request hint
        is an optimization and never a guarantee; ``ImagePart``'s own checks are the domain
        ceiling and cannot enforce a number this deployment chose.

        ``target`` is the third thing the wire cannot guarantee, and it is the one the caller
        cannot re-verify from the pixels: a crop and a shrunk screen are the same blob. So the
        reply carries what the body actually pointed at, and that is what the returned value
        reports, never the ask. An old body that sets nothing reads as ``DISPLAY``, which is
        exactly what such a body can take.

        Attempted exactly once, with ``capture_timeout_s`` of patience. Every failure, including a
        bound the wire cannot carry and a reply this side refuses, becomes ``BodyGatewayError``,
        which the tool turns into a recoverable result rather than an exception.
        """
        try:
            request = CaptureScreenRequest(
                max_edge=max_edge, max_bytes=max_bytes, target=_TARGET_TO_WIRE[target]
            )
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
