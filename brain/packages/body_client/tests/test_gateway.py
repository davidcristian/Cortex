"""Contract tests for GrpcBodyGateway (ADR-0023): a fake BodyService on loopback (127.0.0.1:0,
CI-safe) drives the adapter's mappings end to end over the happy get/set with every optional-field
combination, the token attached and its absence rejected, and gRPC failures → BodyGatewayError.
The capture path (ADR-0029) adds the size story: a happy blob, an empty reply, a bad mime, an
image over the domain budget, a reply the *transport* would refuse without the raised channel
option, and the deadline.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import grpc
import pytest
from grpc import aio

from cortex_body_client import MAX_RECEIVE_BYTES, GrpcBodyGateway
from cortex_core import MAX_IMAGE_BYTES, BodyGatewayError
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
    ) -> None:
        self.level = level
        self.muted = muted
        self.blob = blob
        self.no_image = no_image
        self.capture_delay_s = capture_delay_s
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

    async def GetVolume(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: GetVolumeRequest,
        context: aio.ServicerContext[GetVolumeRequest, VolumeStatePb],
    ) -> VolumeStatePb:
        del request
        await self._ensure_token(context)
        if self._fail is not None:
            await context.abort(self._fail, "device unavailable")
        return VolumeStatePb(level=self.level, muted=self.muted)

    async def SetVolume(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: SetVolumeRequest,
        context: aio.ServicerContext[SetVolumeRequest, VolumeStatePb],
    ) -> VolumeStatePb:
        await self._ensure_token(context)
        if self._fail is not None:
            await context.abort(self._fail, "set failed")
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
        return CaptureScreenReply(image=self.blob)


async def _serve(servicer: BodyServiceServicer) -> tuple[str, aio.Server]:
    server = aio.server()
    add_BodyServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    return f"127.0.0.1:{port}", server


@asynccontextmanager
async def _gateway(
    fake: FakeBody, *, token: str = "", capture_timeout_s: float = 10.0
) -> AsyncGenerator[GrpcBodyGateway]:
    """Serve ``fake`` on loopback, yield a connected gateway, and tear both down (closer too)."""
    endpoint, server = await _serve(fake)
    gateway, close = await GrpcBodyGateway.connect(
        endpoint, token=token, capture_timeout_s=capture_timeout_s
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
    assert fake.captured == CaptureScreenRequest(max_edge=1600, max_bytes=MAX_IMAGE_BYTES)


async def test_capture_screen_defaults_send_no_hints_at_all() -> None:
    fake = FakeBody(blob=_blob())
    async with _gateway(fake) as gateway:
        await gateway.capture_screen()
    assert fake.captured == CaptureScreenRequest(max_edge=0, max_bytes=0)


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


async def test_a_capture_error_maps_to_body_gateway_error() -> None:
    async with _gateway(FakeBody(fail=grpc.StatusCode.PERMISSION_DENIED)) as gateway:
        with pytest.raises(BodyGatewayError, match="capture failed"):
            await gateway.capture_screen()


async def test_an_unimplemented_capture_maps_to_body_gateway_error() -> None:
    async with _gateway(FakeBody(fail=grpc.StatusCode.UNIMPLEMENTED)) as gateway:
        with pytest.raises(BodyGatewayError, match="capture failed"):
            await gateway.capture_screen()


async def test_a_wedged_body_hits_the_capture_deadline() -> None:
    fake = FakeBody(blob=_blob(), capture_delay_s=5.0)
    async with _gateway(fake, capture_timeout_s=0.05) as gateway:
        with pytest.raises(BodyGatewayError, match="capture_screen failed"):
            await gateway.capture_screen()


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
