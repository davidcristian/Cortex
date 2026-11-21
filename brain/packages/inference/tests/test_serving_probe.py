import asyncio

import httpx
import pytest
from drip_server import DripServer
from serving_contract import ALL_CHECKS, Check, ProbeUnderTest

from cortex_core import (
    ModelServer,
    ModelUnavailableError,
    MultiServerModelManager,
    ScriptedServingProbe,
    ServingProbe,
    ServingWatch,
)
from cortex_inference import (
    CORTEX_DOWN,
    CORTEX_LOADING,
    LlamaServerProbe,
    gpu_server_wording,
    subagent_wording,
)

_ENDPOINT = "http://model-host:8080"

# A dripped health header is 57 bytes sent 0.01 s apart, so no read waits near the bound and the
# whole header takes at least twice it.
_BOUND_S = 0.25
_HEADER_BYTES = 57


def _answering(status: int, seen: list[httpx.Request] | None = None) -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json={"status": "ok"})

    return httpx.MockTransport(answer)


def _refusing() -> httpx.MockTransport:
    def refuse(request: httpx.Request) -> httpx.Response:
        msg = "connection refused"
        raise httpx.ConnectError(msg, request=request)

    return httpx.MockTransport(refuse)


def _probe(transport: httpx.AsyncBaseTransport, endpoint: str = _ENDPOINT) -> LlamaServerProbe:
    return LlamaServerProbe(endpoint, transport, timeout_s=0.5)


def _scripted(*, answering: bool) -> ServingProbe:
    return ScriptedServingProbe(answer=None if answering else "the scripted part is down")


def _llama(*, answering: bool) -> ServingProbe:
    return _probe(_answering(200) if answering else _refusing())


@pytest.mark.parametrize("make", [_scripted, _llama], ids=["scripted", "llama-server"])
@pytest.mark.parametrize("check", ALL_CHECKS)
async def test_serving_probe_contract(make: ProbeUnderTest, check: Check) -> None:
    await check(make)


async def test_the_probe_asks_the_servers_own_health_path() -> None:
    seen: list[httpx.Request] = []
    assert await _probe(_answering(200, seen), f"{_ENDPOINT}/").fault() is None
    (request,) = seen
    assert str(request.url) == f"{_ENDPOINT}/health"
    assert request.method == "GET"
    assert request.extensions["timeout"] == httpx.Timeout(0.5).as_dict()


async def test_a_server_that_cannot_be_reached_reads_as_not_answering() -> None:
    assert await _probe(_refusing()).fault() == CORTEX_DOWN


async def test_a_server_still_loading_its_model_reads_as_loading() -> None:
    assert await _probe(_answering(503)).fault() == CORTEX_LOADING


async def test_any_other_status_is_named_in_the_fault() -> None:
    assert await _probe(_answering(500)).fault() == (
        "the usual assistant's model server answered its health check with 500"
    )


def _subagent(transport: httpx.AsyncBaseTransport) -> LlamaServerProbe:
    return LlamaServerProbe(_ENDPOINT, transport, timeout_s=0.5, wording=subagent_wording("qwen"))


async def test_a_subagent_server_probe_names_its_roster_entry() -> None:
    assert _subagent(_answering(200)).part == "the server for subagent model qwen"
    assert await _subagent(_answering(200)).fault() is None
    assert await _subagent(_refusing()).fault() == (
        "the server for subagent model qwen is not answering, so work delegated to it fails"
    )
    assert await _subagent(_answering(503)).fault() == (
        "the server for subagent model qwen is still loading, so work delegated to it fails "
        "until it is up"
    )
    assert await _subagent(_answering(500)).fault() == (
        "the server for subagent model qwen answered its health check with 500"
    )


async def test_a_gpu_server_probe_names_its_address_and_its_roster_entry() -> None:
    def probe(transport: httpx.AsyncBaseTransport) -> LlamaServerProbe:
        wording = gpu_server_wording("qwen", _ENDPOINT)
        return LlamaServerProbe(_ENDPOINT, transport, timeout_s=0.5, wording=wording)

    part = "the GPU server http://model-host:8080 for subagent model qwen"
    assert probe(_answering(200)).part == part
    assert await probe(_answering(200)).fault() is None
    assert await probe(_refusing()).fault() == f"{part} is not answering"
    assert await probe(_answering(503)).fault() == f"{part} is still loading"


async def test_a_silent_scripted_probe_never_answers() -> None:
    probe = ScriptedServingProbe()
    probe.silent = True
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(probe.fault(), timeout=0.01)
    assert probe.calls == 1


def _dripping() -> DripServer:
    return DripServer("/health", b"", drip_head=True)


async def test_a_health_header_dripped_past_the_bound_reads_as_not_answering() -> None:
    async with _dripping().serving() as server, httpx.AsyncHTTPTransport() as transport:
        probe = LlamaServerProbe(server.endpoint, transport, timeout_s=_BOUND_S)
        assert await probe.fault() == CORTEX_DOWN
        assert 0 < server.dripped < _HEADER_BYTES


async def test_a_health_header_dripped_inside_the_bound_reads_as_ready() -> None:
    server = _dripping()
    server.pause_s = 0.001
    async with server.serving(), httpx.AsyncHTTPTransport() as transport:
        assert await LlamaServerProbe(server.endpoint, transport, timeout_s=30.0).fault() is None
        assert server.dripped == _HEADER_BYTES


async def test_a_lease_passes_over_a_gpu_server_whose_health_header_drips_past_the_bound() -> None:
    async with (
        _dripping().serving() as slow,
        DripServer("/unasked", b"").serving() as ready,
        httpx.AsyncHTTPTransport() as transport,
    ):
        manager = MultiServerModelManager(
            "qwen",
            [
                ModelServer(each, probe=LlamaServerProbe(each, transport, timeout_s=_BOUND_S))
                for each in (slow.endpoint, ready.endpoint)
            ],
        )
        async with manager.acquire("qwen") as lease:
            assert lease.endpoint == ready.endpoint
            assert 0 < slow.dripped < _HEADER_BYTES


async def test_a_lease_fails_when_its_only_gpu_server_drips_its_health_header() -> None:
    async with _dripping().serving() as slow, httpx.AsyncHTTPTransport() as transport:
        wording = gpu_server_wording("qwen", slow.endpoint)
        probe = LlamaServerProbe(slow.endpoint, transport, timeout_s=_BOUND_S, wording=wording)
        manager = MultiServerModelManager("qwen", [ModelServer(slow.endpoint, probe=probe)])
        with pytest.raises(ModelUnavailableError, match="for subagent model qwen is not answering"):
            async with manager.acquire("qwen"):
                pass  # pragma: no cover - acquire raises before the body runs
        assert 0 < slow.dripped < _HEADER_BYTES


async def test_the_serving_watch_reports_a_dripped_health_header_in_its_own_words() -> None:
    async with _dripping().serving() as slow, httpx.AsyncHTTPTransport() as transport:
        probe = LlamaServerProbe(slow.endpoint, transport, timeout_s=_BOUND_S)
        watch = ServingWatch([probe], timeout_s=_BOUND_S)
        await watch.refresh()
        assert watch.fault() == "the usual assistant's model server did not answer within 0.25 s"
        assert 0 < slow.dripped < _HEADER_BYTES
