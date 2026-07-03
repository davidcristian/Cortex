"""Behavior tests for the seam token interceptor (assumption 5, ADR-0016).

Wire-level: a real loopback grpc.aio server built by `create_server` with a token. Every
RPC (unary Health, streaming Converse) requires the metadata token, fail closed. Unit-level:
the metadata walk's branches the wire cannot reach (bytes values, absent metadata, an
unserviced method).
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import cast

import grpc
import pytest
from grpc import aio

from cortex_core import EchoInferenceBackend, InMemorySessionStore, SystemClock, TurnEngine
from cortex_orchestrator import (
    SEAM_TOKEN_HEADER,
    SeamServerConfig,
    SeamTokenInterceptor,
    create_server,
)
from cortex_seam import (
    BrainServiceStub,
    ClientEvent,
    HealthReply,
    HealthRequest,
    ServerEvent,
    UserTurn,
)

_TOKEN = "sekrit-seam-token"  # noqa: S105 - a test fixture value, not a real credential
_METADATA = ((SEAM_TOKEN_HEADER, _TOKEN),)


async def _health(stub: BrainServiceStub, metadata: tuple[tuple[str, str], ...]) -> HealthReply:
    health = stub.Health  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("HealthReply", await health(HealthRequest(), metadata=metadata))


def _engine() -> TurnEngine:
    return TurnEngine(InMemorySessionStore(), EchoInferenceBackend(), SystemClock())


@pytest.fixture
async def token_server() -> AsyncIterator[str]:
    """A BrainService requiring the seam token, on an ephemeral loopback port."""
    config = SeamServerConfig(host="127.0.0.1", port=0, token=_TOKEN)
    server, port = create_server(config, _engine())
    await server.start()
    yield f"127.0.0.1:{port}"
    await server.stop(grace=None)


async def test_health_with_the_token_round_trips(token_server: str) -> None:
    async with aio.insecure_channel(token_server) as channel:
        reply = await _health(BrainServiceStub(channel), _METADATA)
    assert reply.ready is True


async def test_health_without_the_token_is_unauthenticated(token_server: str) -> None:
    async with aio.insecure_channel(token_server) as channel:
        with pytest.raises(aio.AioRpcError) as err:
            await _health(BrainServiceStub(channel), ())
    assert err.value.code() is grpc.StatusCode.UNAUTHENTICATED
    assert err.value.details() == "invalid or missing seam token"


async def test_health_with_a_wrong_token_is_unauthenticated(token_server: str) -> None:
    async with aio.insecure_channel(token_server) as channel:
        with pytest.raises(aio.AioRpcError) as err:
            await _health(BrainServiceStub(channel), ((SEAM_TOKEN_HEADER, "guessed-wrong"),))
    assert err.value.code() is grpc.StatusCode.UNAUTHENTICATED


async def test_converse_without_the_token_is_unauthenticated(token_server: str) -> None:
    # The streaming RPC shape: the rejection must arrive as a status, before any turn runs.
    async with aio.insecure_channel(token_server) as channel:
        await asyncio.wait_for(channel.channel_ready(), timeout=10)
        stub = BrainServiceStub(channel)
        converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse())
        await call.write(ClientEvent(session_id="s", user_turn=UserTurn(text="hi")))
        await call.done_writing()
        with pytest.raises(aio.AioRpcError) as err:
            await call.read()
    assert err.value.code() is grpc.StatusCode.UNAUTHENTICATED


async def test_converse_with_the_token_streams_a_turn(token_server: str) -> None:
    async with aio.insecure_channel(token_server) as channel:
        await asyncio.wait_for(channel.channel_ready(), timeout=10)
        stub = BrainServiceStub(channel)
        converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse(metadata=_METADATA))
        await call.write(ClientEvent(session_id="s", user_turn=UserTurn(text="hi")))
        await call.done_writing()
        events = [event async for event in call]
    assert events[-1].WhichOneof("event") == "turn_complete"


# --- unit level: the interceptor's metadata walk, via the public intercept_service -----


@dataclass(frozen=True)
class _Details:
    """A minimal grpc.HandlerCallDetails stand-in for driving the walk directly."""

    method: str
    invocation_metadata: tuple[tuple[str, str | bytes], ...] | None


def _details(*metadata: tuple[str, str | bytes]) -> grpc.HandlerCallDetails:
    return cast("grpc.HandlerCallDetails", _Details("/cortex/Method", metadata))


async def _passes_through(details: grpc.HandlerCallDetails) -> bool:
    """Whether the interceptor returns the continuation's handler untouched (authorized)."""

    async def noop(request: object, context: object) -> object:
        del context
        return request

    handler: grpc.RpcMethodHandler[object, object] = grpc.unary_unary_rpc_method_handler(noop)

    async def continuation(
        inner: grpc.HandlerCallDetails,
    ) -> "grpc.RpcMethodHandler[object, object]":
        del inner
        return handler

    result = await SeamTokenInterceptor(_TOKEN).intercept_service(continuation, details)
    return result is handler


async def test_bytes_metadata_values_authorize() -> None:
    # gRPC metadata values may surface as bytes; the compare must not assume str.
    assert await _passes_through(_details((SEAM_TOKEN_HEADER, _TOKEN.encode()))) is True


async def test_the_walk_skips_unrelated_metadata_keys() -> None:
    details = _details(("user-agent", "grpc-rust/0.0"), (SEAM_TOKEN_HEADER, _TOKEN))
    assert await _passes_through(details) is True


async def test_absent_metadata_is_rejected() -> None:
    absent = cast("grpc.HandlerCallDetails", _Details("/cortex/Method", None))
    assert await _passes_through(absent) is False


async def test_intercept_passes_through_an_unserviced_method() -> None:
    # The continuation may resolve to None (no such method); nothing to guard, propagate it.
    interceptor = SeamTokenInterceptor(_TOKEN)

    async def continuation(details: grpc.HandlerCallDetails) -> None:
        del details

    assert await interceptor.intercept_service(continuation, _details()) is None
