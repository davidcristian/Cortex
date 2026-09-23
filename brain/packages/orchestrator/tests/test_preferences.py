from collections.abc import Mapping
from typing import cast

import grpc
import pytest
from grpc import aio

from cortex_core import (
    EchoInferenceBackend,
    InMemoryPreferenceStore,
    InMemorySessionStore,
    PreferenceStore,
    SystemClock,
    TurnEngine,
)
from cortex_orchestrator import RpcPorts, RpcServerConfig, create_server
from cortex_seam import (
    BrainServiceStub,
    GetPreferencesReply,
    GetPreferencesRequest,
    SetPreferenceReply,
    SetPreferenceRequest,
)


async def _get(stub: BrainServiceStub) -> GetPreferencesReply:
    method = stub.GetPreferences  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("GetPreferencesReply", await method(GetPreferencesRequest()))


async def _set(stub: BrainServiceStub, key: str, value: str) -> SetPreferenceReply:
    method = stub.SetPreference  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("SetPreferenceReply", await method(SetPreferenceRequest(key=key, value=value)))


async def _serve(preferences: PreferenceStore | None) -> tuple[aio.Server, str]:
    """A BrainService whose only wired extra is (optionally) the preference store."""
    store = InMemorySessionStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    server, port = create_server(
        RpcServerConfig(host="127.0.0.1", port=0),
        lambda _confirmer, _progress: engine,
        store,
        RpcPorts(preferences=preferences),
    )
    await server.start()
    return server, f"127.0.0.1:{port}"


async def _round_trip(
    preferences: PreferenceStore | None, writes: list[tuple[str, str]]
) -> Mapping[str, str]:
    """Apply `writes`, then read the record back over gRPC."""
    server, address = await _serve(preferences)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            for key, value in writes:
                await _set(stub, key, value)
            reply = await _get(stub)
    finally:
        await server.stop(grace=None)
    return {pair.key: pair.value for pair in reply.preferences}


async def test_a_written_preference_reads_back_through_the_rpc() -> None:
    stored = await _round_trip(
        InMemoryPreferenceStore(), [("overlay.theme", "midnight"), ("overlay.mark", "foam")]
    )
    assert stored == {"overlay.theme": "midnight", "overlay.mark": "foam"}


async def test_an_empty_value_clears_the_key_over_the_wire() -> None:
    stored = await _round_trip(
        InMemoryPreferenceStore(), [("overlay.theme", "daylight"), ("overlay.theme", "")]
    )
    assert stored == {}


async def test_pairs_come_back_in_a_stable_order() -> None:
    server, address = await _serve(
        InMemoryPreferenceStore(initial={"b.two": "2", "a.one": "1", "c.three": "3"})
    )
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _get(BrainServiceStub(channel))
    finally:
        await server.stop(grace=None)
    assert [pair.key for pair in reply.preferences] == ["a.one", "b.two", "c.three"]


async def test_an_unwired_store_reads_empty_and_accepts_a_write() -> None:
    stored = await _round_trip(None, [("overlay.mark", "ping")])
    assert stored == {}


@pytest.mark.parametrize("failing_call", ["get", "set"])
async def test_a_store_failure_aborts_unavailable(failing_call: str) -> None:
    preferences = InMemoryPreferenceStore()
    preferences.fail_with = "redis is down"
    server, address = await _serve(preferences)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            call = _get(stub) if failing_call == "get" else _set(stub, "overlay.mark", "sheen")
            with pytest.raises(aio.AioRpcError) as excinfo:
                await call
    finally:
        await server.stop(grace=None)
    assert excinfo.value.code() == grpc.StatusCode.UNAVAILABLE
    assert "redis is down" in (excinfo.value.details() or "")
