"""Contract tests for GrpcBodyGateway (ADR-0023): a fake BodyService on loopback (127.0.0.1:0,
CI-safe) drives the adapter's mappings end to end over the happy get/set with every optional-field
combination, the token attached and its absence rejected, and gRPC failures → BodyGatewayError.
The capture path (ADR-0029) adds the size story: a happy blob, an empty reply, a bad mime, an
image over the domain budget, a reply the *transport* would refuse without the raised channel
option, and the deadline.

Since the 2026-08-08 addendum the failure assertions also pin the **kind**: every status the body
can send is driven through the real adapter and its `BodyFailure` checked, because the sentence
the cortex reads is chosen from that kind and a misclassification is exactly how a refused capture
came to be announced as an unreachable body.
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

import grpc
import pytest
from grpc import aio

from cortex_body_client import (
    DEFAULT_CALL_TIMEOUT_S,
    DEFAULT_CAPTURE_TIMEOUT_S,
    MAX_RECEIVE_BYTES,
    GrpcBodyGateway,
)
from cortex_core import MAX_IMAGE_BYTES, BodyFailure, BodyGatewayError, CaptureTarget
from cortex_seam import (
    SEAM_TOKEN_HEADER,
    BodyServiceServicer,
    CaptureScreenReply,
    CaptureScreenRequest,
    GetVolumeRequest,
    ImageBlob,
    NotifyReply,
    NotifyRequest,
    SetVolumeRequest,
    add_BodyServiceServicer_to_server,
)
from cortex_seam import CaptureTarget as CaptureTargetPb
from cortex_seam import VolumeState as VolumeStatePb

_TOKEN = "sekrit-seam-token"  # noqa: S105 - test seam token, not a real secret


class FakeBody(BodyServiceServicer):
    """A scripted fake BodyService: reports/records volume state, optionally requires the token
    or fails a call with a gRPC status. Records which SetVolume fields crossed the wire so the
    adapter's proto explicit-presence handling can be asserted.
    """

    def __init__(  # noqa: PLR0913 - a scripted fake of a five-RPC service, one knob per behaviour
        self,
        *,
        level: float = 0.5,
        muted: bool = False,
        shown: bool = True,
        fail: grpc.StatusCode | None = None,
        require_token: str | None = None,
        blob: ImageBlob | None = None,
        no_image: bool = False,
        capture_delay_s: float = 0.0,
        call_delay_s: float = 0.0,
        resolved_target: CaptureTargetPb = CaptureTargetPb.CAPTURE_TARGET_DISPLAY,
    ) -> None:
        self.level = level
        self.muted = muted
        self.blob = blob
        # Typed as the wire enum, which is an int on this generated surface, so a body naming a
        # target this brain does not know can still be scripted the way a newer body sends one.
        self.resolved_target = resolved_target
        self.no_image = no_image
        self.capture_delay_s = capture_delay_s
        # What a wedged COM call looks like from here: the handler accepted the request and
        # never answers. `off_worker` on the body side is why that is the shape to fake.
        self.call_delay_s = call_delay_s
        self.captured: CaptureScreenRequest | None = None
        self.shown = shown
        self._fail = fail
        self._require_token = require_token
        self.saw_level: bool | None = None
        self.saw_mute: bool | None = None
        self.notified: NotifyRequest | None = None

    async def _ensure_token[Req, Resp](self, context: aio.ServicerContext[Req, Resp]) -> None:
        if self._require_token is None:
            return
        for key, value in context.invocation_metadata() or ():
            if key == SEAM_TOKEN_HEADER and value == self._require_token:
                return
        await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid or missing seam token")

    async def _park(self) -> None:
        """Hold the handler open, the way a COM call parks its thread on a wedged host."""
        if self.call_delay_s:
            await asyncio.sleep(self.call_delay_s)

    async def GetVolume(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: GetVolumeRequest,
        context: aio.ServicerContext[GetVolumeRequest, VolumeStatePb],
    ) -> VolumeStatePb:
        del request
        await self._ensure_token(context)
        if self._fail is not None:
            await context.abort(self._fail, "device unavailable")
        await self._park()
        return VolumeStatePb(level=self.level, muted=self.muted)

    async def SetVolume(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: SetVolumeRequest,
        context: aio.ServicerContext[SetVolumeRequest, VolumeStatePb],
    ) -> VolumeStatePb:
        await self._ensure_token(context)
        if self._fail is not None:
            await context.abort(self._fail, "set failed")
        await self._park()
        self.saw_level = request.HasField("level")
        self.saw_mute = request.HasField("mute")
        if request.HasField("level"):
            self.level = request.level
        if request.HasField("mute"):
            self.muted = request.mute
        return VolumeStatePb(level=self.level, muted=self.muted)

    async def Notify(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: NotifyRequest,
        context: aio.ServicerContext[NotifyRequest, NotifyReply],
    ) -> NotifyReply:
        await self._ensure_token(context)
        if self._fail is not None:
            await context.abort(self._fail, "notify failed")
        await self._park()
        self.notified = request
        return NotifyReply(shown=self.shown)

    async def CaptureScreen(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: CaptureScreenRequest,
        context: aio.ServicerContext[CaptureScreenRequest, CaptureScreenReply],
    ) -> CaptureScreenReply:
        await self._ensure_token(context)
        if self._fail is not None:
            await context.abort(self._fail, "capture failed")
        self.captured = request
        if self.capture_delay_s:
            await asyncio.sleep(self.capture_delay_s)
        if self.no_image:
            return CaptureScreenReply()
        return CaptureScreenReply(image=self.blob, resolved_target=self.resolved_target)


async def _serve(servicer: BodyServiceServicer) -> tuple[str, aio.Server]:
    server = aio.server()
    add_BodyServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    return f"127.0.0.1:{port}", server


@asynccontextmanager
async def _gateway(
    fake: FakeBody,
    *,
    token: str = "",
    capture_timeout_s: float = DEFAULT_CAPTURE_TIMEOUT_S,
    call_timeout_s: float = DEFAULT_CALL_TIMEOUT_S,
) -> AsyncGenerator[GrpcBodyGateway]:
    """Serve ``fake`` on loopback, yield a connected gateway, and tear both down (closer too)."""
    endpoint, server = await _serve(fake)
    gateway, close = await GrpcBodyGateway.connect(
        endpoint, token=token, capture_timeout_s=capture_timeout_s, call_timeout_s=call_timeout_s
    )
    try:
        yield gateway
    finally:
        await close()
        await server.stop(grace=None)


async def test_get_volume_maps_the_reply() -> None:
    # The wire level is a 32-bit float, so compare it with approx (0.3 → 0.30000001…).
    async with _gateway(FakeBody(level=0.3, muted=True)) as gateway:
        state = await gateway.get_volume()
    assert state.level == pytest.approx(0.3)
    assert state.muted is True


async def test_get_volume_error_maps_to_body_gateway_error() -> None:
    async with _gateway(FakeBody(fail=grpc.StatusCode.INTERNAL)) as gateway:
        with pytest.raises(BodyGatewayError, match="device unavailable"):
            await gateway.get_volume()


async def test_set_volume_sends_level_and_mute() -> None:
    fake = FakeBody(level=0.1, muted=False)
    async with _gateway(fake) as gateway:
        state = await gateway.set_volume(level=0.8, mute=True)
    assert state.level == pytest.approx(0.8)
    assert state.muted is True
    assert (fake.saw_level, fake.saw_mute) == (True, True)


async def test_set_volume_level_only_leaves_mute_unset() -> None:
    fake = FakeBody(level=0.1, muted=True)
    async with _gateway(fake) as gateway:
        await gateway.set_volume(level=0.5)
    assert (fake.saw_level, fake.saw_mute) == (True, False)


async def test_set_volume_mute_only_leaves_level_unset() -> None:
    fake = FakeBody(level=0.1, muted=False)
    async with _gateway(fake) as gateway:
        await gateway.set_volume(mute=True)
    assert (fake.saw_level, fake.saw_mute) == (False, True)


async def test_set_volume_neither_field_set() -> None:
    fake = FakeBody(level=0.2, muted=False)
    async with _gateway(fake) as gateway:
        state = await gateway.set_volume()
    assert state.level == pytest.approx(0.2)
    assert state.muted is False
    assert (fake.saw_level, fake.saw_mute) == (False, False)


async def test_set_volume_error_maps_to_body_gateway_error() -> None:
    async with _gateway(FakeBody(fail=grpc.StatusCode.UNAVAILABLE)) as gateway:
        with pytest.raises(BodyGatewayError, match="set failed"):
            await gateway.set_volume(mute=True)


async def test_notify_round_trips_the_toast_and_the_shown_verdict() -> None:
    fake = FakeBody(shown=True)
    async with _gateway(fake) as gateway:
        shown = await gateway.notify(
            title="Reminder", body="stretch", reminder_id="r1", tainted=True
        )
    assert shown is True
    assert fake.notified is not None
    assert fake.notified.title == "Reminder"
    assert fake.notified.body == "stretch"
    assert fake.notified.reminder_id == "r1"
    assert fake.notified.tainted is True


async def test_notify_not_shown_comes_back_false() -> None:
    async with _gateway(FakeBody(shown=False)) as gateway:
        assert await gateway.notify(title="t", body="b", reminder_id="r1") is False


async def test_notify_unimplemented_maps_to_body_gateway_error() -> None:
    # The body's shape-now answer until its toast lands (ADR-0025): a push failure.
    async with _gateway(FakeBody(fail=grpc.StatusCode.UNIMPLEMENTED)) as gateway:
        with pytest.raises(BodyGatewayError, match="notify failed"):
            await gateway.notify(title="t", body="b", reminder_id="r1")


async def test_token_is_attached_when_configured() -> None:
    async with _gateway(FakeBody(require_token=_TOKEN), token=_TOKEN) as gateway:
        assert (await gateway.get_volume()).level == pytest.approx(0.5)


async def test_missing_token_is_rejected_as_body_gateway_error() -> None:
    # The gateway is built without a token (the empty-metadata branch); the body demands one.
    async with _gateway(FakeBody(require_token=_TOKEN)) as gateway:
        with pytest.raises(BodyGatewayError, match="invalid or missing seam token"):
            await gateway.get_volume()


def _png(size: int) -> bytes:
    """A byte string long enough to stand in for an encoded image of ``size`` bytes."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * (size - 8)


def _blob(*, data_size: int = 64, mime: str = "image/png", **fields: int) -> ImageBlob:
    """One wire blob, with sane defaults a test can override field by field."""
    return ImageBlob(
        data=_png(data_size),
        mime_type=mime,
        width=fields.get("width", 1600),
        height=fields.get("height", 900),
        source_width=fields.get("source_width", 2560),
        source_height=fields.get("source_height", 1440),
        captured_at_unix_ms=fields.get("captured_at_unix_ms", 1_784_000_043_000),
    )


async def test_capture_screen_maps_the_blob_and_sends_both_hints() -> None:
    fake = FakeBody(blob=_blob())
    async with _gateway(fake) as gateway:
        capture = await gateway.capture_screen(max_edge=1600, max_bytes=MAX_IMAGE_BYTES)

    assert capture.image.mime_type == "image/png"
    assert (capture.image.width, capture.image.height) == (1600, 900)
    assert (capture.source_width, capture.source_height) == (2560, 1440)
    assert capture.captured_at.isoformat() == "2026-07-14T03:34:03+00:00"
    assert capture.downscaled is True
    assert capture.target is CaptureTarget.DISPLAY
    assert fake.captured == CaptureScreenRequest(max_edge=1600, max_bytes=MAX_IMAGE_BYTES)


async def test_capture_screen_defaults_send_no_hints_at_all() -> None:
    fake = FakeBody(blob=_blob())
    async with _gateway(fake) as gateway:
        await gateway.capture_screen()
    assert fake.captured == CaptureScreenRequest(max_edge=0, max_bytes=0)


async def test_the_target_reaches_the_wire_as_the_enum_the_body_reads() -> None:
    fake = FakeBody(blob=_blob())
    async with _gateway(fake) as gateway:
        await gateway.capture_screen(target=CaptureTarget.FOCUS)
    assert fake.captured is not None
    assert fake.captured.target == CaptureTargetPb.CAPTURE_TARGET_FOCUS


async def test_what_the_body_says_it_pointed_at_is_what_the_capture_reports() -> None:
    """The one thing on this reply the receiver cannot re-derive from the payload: a crop and a
    shrunk screen are the same blob, and `source_width`/`source_height` are the display's on
    both paths. So the answer is read off the reply and never off the ask."""
    fake = FakeBody(blob=_blob(), resolved_target=CaptureTargetPb.CAPTURE_TARGET_FOCUS)
    async with _gateway(fake) as gateway:
        capture = await gateway.capture_screen(target=CaptureTarget.DISPLAY)
    assert capture.target is CaptureTarget.FOCUS


async def test_a_body_that_names_no_target_reads_as_the_whole_display() -> None:
    """A body predating the field leaves the proto3 zero, which is DISPLAY, and that is a
    reading rather than a guess: the only picture such a body can take is the whole display."""
    fake = FakeBody(blob=_blob())
    async with _gateway(fake) as gateway:
        capture = await gateway.capture_screen(target=CaptureTarget.FOCUS)
    assert capture.target is CaptureTarget.DISPLAY


async def test_a_target_this_brain_does_not_know_reads_as_the_whole_display() -> None:
    """Proto3's own rule for an unrecognized enum, spent here rather than raising: a newer body
    naming a third target still sent a picture, and the honest thing this brain can say about it
    is the screen it came off."""
    fake = FakeBody(blob=_blob(), resolved_target=cast("CaptureTargetPb", 99))
    async with _gateway(fake) as gateway:
        capture = await gateway.capture_screen()
    assert capture.target is CaptureTarget.DISPLAY


async def test_a_capture_at_the_display_size_is_not_downscaled() -> None:
    fake = FakeBody(blob=_blob(width=800, height=600, source_width=800, source_height=600))
    async with _gateway(fake) as gateway:
        capture = await gateway.capture_screen()
    assert capture.downscaled is False


async def test_a_body_that_omits_the_source_size_reports_the_image_size() -> None:
    # An older body leaves the new fields at their proto3 zeros; reporting 0x0 as the display
    # size would make the tool tell the model it is looking at a shrunk view of nothing.
    fake = FakeBody(blob=_blob(width=640, height=360, source_width=0, source_height=0))
    async with _gateway(fake) as gateway:
        capture = await gateway.capture_screen()
    assert (capture.source_width, capture.source_height) == (640, 360)
    assert capture.downscaled is False


async def test_a_reply_with_no_image_is_refused() -> None:
    async with _gateway(FakeBody(no_image=True)) as gateway:
        with pytest.raises(BodyGatewayError, match="returned no image"):
            await gateway.capture_screen()


async def test_a_blob_with_no_bytes_is_refused() -> None:
    async with _gateway(FakeBody(blob=ImageBlob(mime_type="image/png", width=4, height=4))) as g:
        with pytest.raises(BodyGatewayError, match="carries no bytes"):
            await g.capture_screen()


async def test_a_blob_with_an_unlisted_mime_is_refused() -> None:
    async with _gateway(FakeBody(blob=_blob(mime="image/gif"))) as gateway:
        with pytest.raises(BodyGatewayError, match="unsupported image type 'image/gif'"):
            await gateway.capture_screen()


async def test_a_blob_with_an_impossible_size_is_refused() -> None:
    async with _gateway(FakeBody(blob=_blob(width=0))) as gateway:
        with pytest.raises(BodyGatewayError, match="image width 0 is outside"):
            await gateway.capture_screen()


async def test_a_body_that_ignores_the_edge_hint_is_refused_on_receipt() -> None:
    """The hint is an optimization; the bound is what the receiver checks.

    Under proto3 an older body ignores ``max_edge`` entirely and answers full resolution, so a
    deployment that asked for 1280 px would otherwise be handed a 4K screen and pay for it in
    bytes and in base64 inflation every later round of the turn. The domain constants cannot
    catch this: 3840 is inside ``MAX_IMAGE_EDGE`` and the blob is inside 6 MiB.
    """
    fake = FakeBody(blob=_blob(width=3840, height=2160))
    async with _gateway(fake) as gateway:
        with pytest.raises(
            BodyGatewayError, match="answered 3840x2160, over the 1280 px edge it was asked for"
        ):
            await gateway.capture_screen(max_edge=1280, max_bytes=MAX_IMAGE_BYTES)


async def test_a_body_that_ignores_the_byte_hint_is_refused_on_receipt() -> None:
    """The same for the byte budget: a reply inside the 6 MiB domain ceiling but over the number
    this deployment configured is a bound the body did not honour, and the brain holds it."""
    fake = FakeBody(blob=_blob(data_size=2_000_000))
    async with _gateway(fake) as gateway:
        with pytest.raises(
            BodyGatewayError, match="answered 2000000 bytes, over the 1000000 byte budget"
        ):
            await gateway.capture_screen(max_edge=1600, max_bytes=1_000_000)


async def test_asking_for_no_bounds_holds_the_reply_to_the_domain_ceiling_alone() -> None:
    """The control arm, and the reason the check reads the request rather than a constant: a zero
    asked for the body's own default, so the very same full-resolution reply is legitimate."""
    fake = FakeBody(blob=_blob(width=3840, height=2160, data_size=2_000_000))
    async with _gateway(fake) as gateway:
        capture = await gateway.capture_screen()
    assert (capture.image.width, capture.image.height) == (3840, 2160)


async def test_a_bound_the_wire_cannot_carry_fails_the_capture_rather_than_the_turn() -> None:
    """``BodyGatewayError`` is this port's only failure channel, and the request is built inside
    it: a bound outside uint32 used to escape as a bare ``ValueError``, which neither the tool
    nor the dispatcher catches, so a misconfigured deployment killed the whole stream."""
    async with _gateway(FakeBody(blob=_blob())) as gateway:
        with pytest.raises(BodyGatewayError, match="a bound the wire cannot carry"):
            await gateway.capture_screen(max_edge=-1)


async def test_a_capture_error_maps_to_body_gateway_error() -> None:
    async with _gateway(FakeBody(fail=grpc.StatusCode.PERMISSION_DENIED)) as gateway:
        with pytest.raises(BodyGatewayError, match="capture failed"):
            await gateway.capture_screen()


async def test_an_unimplemented_capture_maps_to_body_gateway_error() -> None:
    async with _gateway(FakeBody(fail=grpc.StatusCode.UNIMPLEMENTED)) as gateway:
        with pytest.raises(BodyGatewayError, match="capture failed"):
            await gateway.capture_screen()


# A wedged handler parks far longer than either deadline under test, so whichever fires is
# production's and never the fake running out of sleep.
_WEDGED_S = 5.0
# The deadline the gateway is driven at: short enough that a suite notices nothing.
_IMPATIENT_S = 0.05
# How long a deadline test may take before the TEST fails, twenty times production's deadline and
# a fiftieth of the fake's park. It exists so a dropped ``timeout=`` reddens the suite instead of
# hanging it: an unbounded call is a test that never returns, which reports nothing to anyone.
_TEST_PATIENCE_S = 1.0

# The kinds that mean the body answered and said something. Our own expired deadline must never
# be classified into this set: that is the mistake the other direction of this seam found the
# hard way, where tonic's own expiry arrives as a sourceless ``Cancelled`` and reads as a reply
# (ADR-0024's deadline addendum). grpc-python does not have that shape, spending
# ``DEADLINE_EXCEEDED`` for its own expiry, but the property is worth pinning rather than
# inheriting: what makes it safe is the classification, not the library.
_THE_BODY_ANSWERED = (
    BodyFailure.REFUSED,
    BodyFailure.UNSUPPORTED,
    BodyFailure.UNREADY,
    BodyFailure.OVERSIZE,
)


async def test_a_wedged_body_hits_the_capture_deadline() -> None:
    fake = FakeBody(blob=_blob(), capture_delay_s=_WEDGED_S)
    async with _gateway(fake, capture_timeout_s=_IMPATIENT_S) as gateway:
        async with asyncio.timeout(_TEST_PATIENCE_S):
            with pytest.raises(BodyGatewayError, match="capture_screen failed") as caught:
                await gateway.capture_screen()
    assert caught.value.kind is BodyFailure.UNREACHABLE


# The three calls that carry the short deadline, each as the name its failure message spells and
# the one-liner that drives it. Annotated rather than inferred: the parameter's type is what the
# lambdas are read against, and without it every method access under them is unknown.
_SHORT_DEADLINE_CALLS: tuple[tuple[str, Callable[[GrpcBodyGateway], Awaitable[object]]], ...] = (
    ("get_volume", lambda gateway: gateway.get_volume()),
    ("set_volume", lambda gateway: gateway.set_volume(level=0.5)),
    ("notify", lambda gateway: gateway.notify(title="t", body="b", reminder_id="r")),
)


@pytest.mark.parametrize(("name", "call"), _SHORT_DEADLINE_CALLS)
async def test_a_wedged_body_hits_the_call_deadline_on_every_other_call(
    name: str, call: Callable[[GrpcBodyGateway], Awaitable[object]]
) -> None:
    """The three calls that used to have no deadline at all now have one, and the reason is the
    body's own design: every handler runs on ``spawn_blocking`` because Core Audio and the toast
    manager are COM, and a COM call parks its thread for as long as the host takes. Nothing above
    this adapter bounds a tool call, so an unbounded read of a wedged endpoint hung the turn.

    The kind is pinned twice over, once positively and once against the set that would be a lie:
    a deadline this side chose is the absence of an answer, so it may say the body could not be
    reached and may never be worded as something the body said.
    """
    async with _gateway(FakeBody(call_delay_s=_WEDGED_S), call_timeout_s=_IMPATIENT_S) as gateway:
        async with asyncio.timeout(_TEST_PATIENCE_S):
            with pytest.raises(BodyGatewayError, match=f"body {name} failed") as caught:
                await call(gateway)
    assert caught.value.kind is BodyFailure.UNREACHABLE
    assert caught.value.kind not in _THE_BODY_ANSWERED


async def test_the_short_deadline_does_not_bound_a_capture() -> None:
    """Two knobs rather than one, and this is the difference between them. A capture slower than
    a volume read is a healthy capture, not a wedged host, so the short deadline must not reach
    it; folding both onto one number would either end a legitimate blit or hand a volume read ten
    seconds of patience it can never spend."""
    fake = FakeBody(blob=_blob(), capture_delay_s=_IMPATIENT_S * 4)
    async with _gateway(fake, call_timeout_s=_IMPATIENT_S) as gateway:
        capture = await gateway.capture_screen()
    assert (capture.image.width, capture.image.height) == (1600, 900)


def test_the_raised_receive_limit_is_the_number_it_claims_to_be() -> None:
    # Against the literal, because every other assertion about this option compares production's
    # own constant to itself: the pair below reads `oversized < MAX_RECEIVE_BYTES`, so raising the
    # limit is invisible to them. 16 MiB deliberately sits above both the body's 6 MiB ceiling and
    # the domain budget, so a reply that breaks the domain bound is refused by the domain.
    assert MAX_RECEIVE_BYTES == 16777216


async def test_an_oversized_reply_crosses_the_transport_and_is_refused_by_the_domain() -> None:
    # The distrust-green proof, in two halves. This reply is 8 MiB: over grpc's own 4 MiB
    # receive default (so the raised channel option is doing work), and over the 6 MiB domain
    # budget (so the bound that refuses it is the one the cortex can be told about).
    oversized = MAX_IMAGE_BYTES + 2 * 1024 * 1024
    assert 4 * 1024 * 1024 < oversized < MAX_RECEIVE_BYTES
    fake = FakeBody(blob=_blob(data_size=oversized))
    async with _gateway(fake) as gateway:
        with pytest.raises(BodyGatewayError, match="over the 6291456 byte budget"):
            await gateway.capture_screen()


async def test_the_unraised_default_would_have_killed_that_reply_in_the_transport() -> None:
    # The other half: the same reply against a channel left at grpc's default is refused by the
    # transport with a message about bytes, not about screens. Without the option the domain
    # bound above could never run, so the two tests together pin why the option exists.
    oversized = MAX_IMAGE_BYTES + 2 * 1024 * 1024
    fake = FakeBody(blob=_blob(data_size=oversized))
    endpoint, server = await _serve(fake)
    channel = aio.insecure_channel(endpoint)
    gateway = GrpcBodyGateway(channel)
    try:
        with pytest.raises(BodyGatewayError, match="Received message larger than max"):
            await gateway.capture_screen()
    finally:
        await channel.close()
        await server.stop(grace=None)


# Every status the body's own handlers can send, with the sentence they send it with, taken from
# `body/crates/rpc/src/screen.rs`, `server.rs` and `auth.rs`. The kind column is what the cortex's
# wording is chosen from, so this table is the classification contract in one place.
_BODY_STATUSES = [
    pytest.param(
        grpc.StatusCode.PERMISSION_DENIED,
        "screen capture is disabled on this host",
        BodyFailure.REFUSED,
        id="capture switched off, the shipping default",
    ),
    pytest.param(
        grpc.StatusCode.RESOURCE_EXHAUSTED,
        "the capture is too large for the seam: 6291457 bytes",
        BodyFailure.OVERSIZE,
        id="too large even after the shrink ladder",
    ),
    pytest.param(
        grpc.StatusCode.FAILED_PRECONDITION,
        "no display: lid shut",
        BodyFailure.UNREADY,
        id="no display",
    ),
    pytest.param(
        grpc.StatusCode.INTERNAL,
        "screen capture backend error: BitBlt 0x2",
        BodyFailure.FAULTED,
        id="a backend fault",
    ),
    pytest.param(
        grpc.StatusCode.UNIMPLEMENTED,
        "screen capture lands in a later slice",
        BodyFailure.UNSUPPORTED,
        id="a body older than the brain",
    ),
    pytest.param(
        grpc.StatusCode.UNAUTHENTICATED,
        "invalid or missing seam token",
        BodyFailure.REFUSED,
        id="a rejected seam token",
    ),
    pytest.param(
        grpc.StatusCode.UNAVAILABLE,
        "no display: lid shut",
        BodyFailure.UNREACHABLE,
        id="an older body still spending UNAVAILABLE on host state",
    ),
    pytest.param(
        grpc.StatusCode.DATA_LOSS,
        "something nobody classified",
        BodyFailure.FAULTED,
        id="a code the table does not name",
    ),
]


@pytest.mark.parametrize(("code", "detail", "kind"), _BODY_STATUSES)
async def test_every_status_the_body_sends_is_classified(
    code: grpc.StatusCode, detail: str, kind: BodyFailure
) -> None:
    del detail  # the fake writes its own sentence; the classification is what is under test
    async with _gateway(FakeBody(fail=code)) as gateway:
        with pytest.raises(BodyGatewayError) as caught:
            await gateway.capture_screen()
    assert caught.value.kind is kind


@pytest.mark.parametrize(("code", "detail", "kind"), _BODY_STATUSES)
async def test_the_volume_and_notify_calls_classify_the_same_way(
    code: grpc.StatusCode, detail: str, kind: BodyFailure
) -> None:
    """One classifier, four calls. A per-call copy of the table is how the volume built-in ends
    up wording a failure differently from the capture built-in for the same wire status."""
    del detail
    async with _gateway(FakeBody(fail=code)) as gateway:
        for call in (
            gateway.get_volume(),
            gateway.set_volume(mute=True),
            gateway.notify(title="t", body="b", reminder_id="r1"),
        ):
            with pytest.raises(BodyGatewayError) as caught:
                await call
            assert caught.value.kind is kind


async def test_a_body_that_is_not_there_is_the_only_unreachable_one() -> None:
    """The row the old prefix was true for, and the reason UNAVAILABLE is now reserved: nothing
    the body writes spends that code, so a synthesized one means the call never arrived."""
    gateway, close = await GrpcBodyGateway.connect("127.0.0.1:1", capture_timeout_s=0.2)
    try:
        with pytest.raises(BodyGatewayError) as caught:
            await gateway.capture_screen()
    finally:
        await close()
    assert caught.value.kind is BodyFailure.UNREACHABLE


async def test_a_brain_side_refusal_is_a_fault_and_never_an_unreachable_body() -> None:
    """The four refusals that never touch a status code (a reply with no image, an unusable
    image, a reply outside the bound asked for, a bound the wire cannot carry) take the default,
    and the default must not be the claim this change exists to remove."""
    async with _gateway(FakeBody(no_image=True)) as gateway:
        with pytest.raises(BodyGatewayError) as caught:
            await gateway.capture_screen()
        assert caught.value.kind is BodyFailure.FAULTED

        with pytest.raises(BodyGatewayError) as bad_bound:
            await gateway.capture_screen(max_edge=-1)
        assert bad_bound.value.kind is BodyFailure.FAULTED
