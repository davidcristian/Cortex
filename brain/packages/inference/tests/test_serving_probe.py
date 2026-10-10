import asyncio

import httpx
import pytest
from serving_contract import ALL_CHECKS, Check, ProbeUnderTest

from cortex_core import ScriptedServingProbe, ServingProbe
from cortex_inference import CORTEX_DOWN, CORTEX_LOADING, LlamaServerProbe, subagent_wording

_ENDPOINT = "http://model-host:8080"


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


async def test_a_silent_scripted_probe_never_answers() -> None:
    probe = ScriptedServingProbe()
    probe.silent = True
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(probe.fault(), timeout=0.01)
    assert probe.calls == 1
