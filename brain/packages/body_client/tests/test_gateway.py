"""Contract tests for GrpcBodyGateway (ADR-0023): a fake BodyService on loopback (127.0.0.1:0,
CI-safe) drives the adapter's mappings end to end over the happy get/set with every optional-field
combination, the token attached and its absence rejected, and gRPC failures → BodyGatewayError.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import grpc
import pytest
from grpc import aio

from cortex_body_client import GrpcBodyGateway
from cortex_core import BodyGatewayError
from cortex_seam import (
    SEAM_TOKEN_HEADER,
    BodyServiceServicer,
    GetVolumeRequest,
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

    def __init__(
        self,
        *,
        level: float = 0.5,
        muted: bool = False,
        shown: bool = True,
        fail: grpc.StatusCode | None = None,
        require_token: str | None = None,
    ) -> None:
        self.level = level
        self.muted = muted
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


async def _serve(servicer: BodyServiceServicer) -> tuple[str, aio.Server]:
    server = aio.server()
    add_BodyServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    return f"127.0.0.1:{port}", server


@asynccontextmanager
async def _gateway(fake: FakeBody, *, token: str = "") -> AsyncGenerator[GrpcBodyGateway]:
    """Serve ``fake`` on loopback, yield a connected gateway, and tear both down (closer too)."""
    endpoint, server = await _serve(fake)
    gateway, close = await GrpcBodyGateway.connect(endpoint, token=token)
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
