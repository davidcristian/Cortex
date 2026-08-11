"""Both `BodyGateway` implementations against the same checks (`gateway_contract.py`).

The core's `InMemoryBodyGateway` and the real `GrpcBodyGateway` talking to a `BodyService` served
on loopback (127.0.0.1:0, CI-safe), so nothing is stubbed on the adapter's side of the port: the
requests are real protobuf, the calls cross a real HTTP/2 connection, and the replies come back
through the generated stub. The serving body imitates the Windows one on the one thing the port
says the body decides, the volume clamp; everything else it does is record what it heard.

The adapter's own edge cases (the seam token, every gRPC status mapped to a `BodyFailure` kind, a
reply with no image at all, a blob the transport would refuse, the capture deadline) stay in
`test_gateway.py`, which is where a claim about the wire belongs. This file holds only what both
implementations owe.
"""

from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import grpc
import pytest
from gateway_contract import ALL_CHECKS, CONTRACT_CAPTURE, Check, GatewayUnderTest
from grpc import aio

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    BodyGatewayError,
    CaptureAsk,
    CaptureTarget,
    InMemoryBodyGateway,
    SentNotification,
)
from cortex_seam import (
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

type Build = Callable[[], AbstractAsyncContextManager[GatewayUnderTest]]

_TARGET_FROM_WIRE = {
    int(CaptureTargetPb.CAPTURE_TARGET_DISPLAY): CaptureTarget.DISPLAY,
    int(CaptureTargetPb.CAPTURE_TARGET_FOCUS): CaptureTarget.FOCUS,
}
_GONE = "the body has gone away"


def _contract_blob() -> ImageBlob:
    """`CONTRACT_CAPTURE` as the wire message a body would send for it."""
    image = CONTRACT_CAPTURE.image
    return ImageBlob(
        data=image.data,
        mime_type=image.mime_type,
        width=image.width,
        height=image.height,
        source_width=CONTRACT_CAPTURE.source_width,
        source_height=CONTRACT_CAPTURE.source_height,
        captured_at_unix_ms=int(CONTRACT_CAPTURE.captured_at.timestamp() * 1000),
    )


class ServingBody(BodyServiceServicer):
    """A `BodyService` that behaves the way the port says a body behaves.

    It holds a volume state and clamps a written level, which is the Windows backend's own rule
    and the one place the port puts a decision on the body's side; it answers the contract's fixed
    capture whatever it is asked for, exactly as a real body answers what it photographed rather
    than what was requested; and it records every notify and capture request so a check can see
    what crossed. `broken` aborts every call, which is a body that has gone away.
    """

    def __init__(self) -> None:
        self.level = 0.5
        self.muted = False
        self.shown = True
        self.broken = False
        self.notified: list[NotifyRequest] = []
        self.captured: list[CaptureScreenRequest] = []

    async def _guard[Req, Resp](self, context: aio.ServicerContext[Req, Resp]) -> None:
        if self.broken:
            await context.abort(grpc.StatusCode.UNAVAILABLE, _GONE)

    async def GetVolume(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: GetVolumeRequest,
        context: aio.ServicerContext[GetVolumeRequest, VolumeStatePb],
    ) -> VolumeStatePb:
        del request
        await self._guard(context)
        return VolumeStatePb(level=self.level, muted=self.muted)

    async def SetVolume(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: SetVolumeRequest,
        context: aio.ServicerContext[SetVolumeRequest, VolumeStatePb],
    ) -> VolumeStatePb:
        await self._guard(context)
        if request.HasField("level"):
            self.level = min(1.0, max(0.0, request.level))
        if request.HasField("mute"):
            self.muted = request.mute
        return VolumeStatePb(level=self.level, muted=self.muted)

    async def Notify(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self, request: NotifyRequest, context: aio.ServicerContext[NotifyRequest, NotifyReply]
    ) -> NotifyReply:
        await self._guard(context)
        self.notified.append(request)
        return NotifyReply(shown=self.shown)

    async def CaptureScreen(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: CaptureScreenRequest,
        context: aio.ServicerContext[CaptureScreenRequest, CaptureScreenReply],
    ) -> CaptureScreenReply:
        await self._guard(context)
        self.captured.append(request)
        return CaptureScreenReply(
            image=_contract_blob(), resolved_target=CaptureTargetPb.CAPTURE_TARGET_DISPLAY
        )


@asynccontextmanager
async def _in_memory() -> AsyncGenerator[GatewayUnderTest]:
    gateway = InMemoryBodyGateway(level=0.5, muted=False, capture=CONTRACT_CAPTURE)
    yield GatewayUnderTest(
        gateway=gateway,
        decline_notifications=lambda: gateway.show_notifications(shown=False),
        break_body=lambda: gateway.fail_with(BodyGatewayError(_GONE)),
        notifications=lambda: gateway.notifications,
        captures=lambda: gateway.captures,
    )


def _declined(body: ServingBody) -> None:
    body.shown = False


def _broken(body: ServingBody) -> None:
    body.broken = True


def _heard(body: ServingBody) -> Sequence[SentNotification]:
    return tuple(
        SentNotification(
            title=request.title,
            body=request.body,
            reminder_id=request.reminder_id,
            tainted=request.tainted,
        )
        for request in body.notified
    )


def _asked(body: ServingBody) -> Sequence[CaptureAsk]:
    return tuple(
        CaptureAsk(
            max_edge=request.max_edge,
            max_bytes=request.max_bytes,
            target=_TARGET_FROM_WIRE[request.target],
        )
        for request in body.captured
    )


@asynccontextmanager
async def _grpc() -> AsyncGenerator[GatewayUnderTest]:
    """The real adapter against a real `BodyService` on loopback, torn down after the check."""
    body = ServingBody()
    server = aio.server()
    add_BodyServiceServicer_to_server(body, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    gateway, close = await GrpcBodyGateway.connect(f"127.0.0.1:{port}")
    try:
        yield GatewayUnderTest(
            gateway=gateway,
            decline_notifications=lambda: _declined(body),
            break_body=lambda: _broken(body),
            notifications=lambda: _heard(body),
            captures=lambda: _asked(body),
        )
    finally:
        await close()
        await server.stop(grace=None)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_in_memory, _grpc], ids=["in-memory", "grpc"])
async def test_the_contract_holds(check: Check, build: Build) -> None:
    async with build() as under_test:
        await check(under_test)
