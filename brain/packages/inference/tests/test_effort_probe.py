import httpx
import pytest
from effort_servers import NO_EFFORT_CAPS, QWEN38_CAPS

from cortex_core import ReasoningEffort
from cortex_inference.effort_probe import (
    EFFORT_PROBE_TIMEOUT_S,
    EffortProbeError,
    effort_wire_name,
)

_ENDPOINT = "http://model-host:8081"


async def _ask(response: httpx.Response, effort: ReasoningEffort) -> str | None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await effort_wire_name(_ENDPOINT, effort, client)


def _props(caps: object) -> httpx.Response:
    return httpx.Response(200, json={"chat_template_caps": caps, "build_info": "b12375"})


async def test_the_probe_reads_the_servers_properties_under_its_own_timeout() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _props(QWEN38_CAPS)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await effort_wire_name(f"{_ENDPOINT}/", ReasoningEffort.LOW, client)
    (request,) = seen
    assert request.method == "GET"
    assert str(request.url) == f"{_ENDPOINT}/props"
    assert request.extensions["timeout"]["read"] == EFFORT_PROBE_TIMEOUT_S


@pytest.mark.parametrize(
    ("effort", "name"),
    [
        (ReasoningEffort.LOW, "low"),
        (ReasoningEffort.MEDIUM, "medium"),
        (ReasoningEffort.HIGH, "xhigh"),
    ],
)
async def test_each_level_is_sent_under_a_name_the_qwen38_server_lists(
    effort: ReasoningEffort, name: str
) -> None:
    assert await _ask(_props(QWEN38_CAPS), effort) == name


async def test_the_top_level_is_sent_as_high_where_the_server_lists_it() -> None:
    caps = {"supports_reasoning_effort": True, "reasoning_effort_levels": ["high", "xhigh"]}
    assert await _ask(_props(caps), ReasoningEffort.HIGH) == "high"


@pytest.mark.parametrize("effort", list(ReasoningEffort))
async def test_a_build_that_lists_no_levels_is_sent_the_levels_own_name(
    effort: ReasoningEffort,
) -> None:
    assert await _ask(_props({"supports_reasoning_effort": True}), effort) == effort.value


@pytest.mark.parametrize("levels", [["low", "high"], []])
async def test_a_level_the_server_does_not_list_is_not_sent(levels: list[str]) -> None:
    caps = {"supports_reasoning_effort": True, "reasoning_effort_levels": levels}
    assert await _ask(_props(caps), ReasoningEffort.MEDIUM) is None


@pytest.mark.parametrize(
    "caps",
    [
        NO_EFFORT_CAPS,
        {"supports_system_role": True},
        {"supports_reasoning_effort": "true", "reasoning_effort_levels": ["medium"]},
        {"supports_reasoning_effort": False, "reasoning_effort_levels": ["medium"]},
    ],
)
async def test_a_template_that_does_not_report_the_capability_is_sent_nothing(
    caps: dict[str, object],
) -> None:
    assert await _ask(_props(caps), ReasoningEffort.MEDIUM) is None


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(503, json={"error": {"message": "Loading model"}}), "HTTP 503"),
        (httpx.Response(200, content=b"<html>"), "not JSON"),
        (httpx.Response(200, json=["chat_template_caps"]), "no template capabilities"),
        (httpx.Response(200, json={"build_info": "b10680"}), "no template capabilities"),
        (httpx.Response(200, json={"chat_template_caps": True}), "no template capabilities"),
    ],
)
async def test_an_answer_the_probe_cannot_read_raises(
    response: httpx.Response, reason: str
) -> None:
    with pytest.raises(EffortProbeError, match=reason):
        await _ask(response, ReasoningEffort.MEDIUM)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (httpx.ConnectError("no route to host"), "ConnectError: no route to host"),
        (httpx.ReadTimeout("no answer in time"), "ReadTimeout: no answer in time"),
    ],
)
async def test_a_request_that_fails_or_times_out_raises_naming_the_transport_error(
    error: httpx.TransportError, reason: str
) -> None:
    def refuse(_request: httpx.Request) -> httpx.Response:
        raise error

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as client:
        with pytest.raises(EffortProbeError, match=reason):
            await effort_wire_name(_ENDPOINT, ReasoningEffort.MEDIUM, client)
