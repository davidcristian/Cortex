"""The vision probe (ADR-0029): what CORTEX_VISION resolves to, and what a live /props says.

The probe exists because a brain-side declaration can disagree with the running server, and
both directions of that disagreement are bad: advertising vision the server lacks spends the
whole privacy cost of a screen read on an image nothing can read, and hiding vision the server
has silently removes the capability.
"""

import httpx
import pytest

from cortex_orchestrator.vision import PROBE_TIMEOUT_S, probe_vision, vision_enabled


def _client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # pyright: ignore[reportArgumentType]


async def test_a_server_reporting_vision_is_believed() -> None:
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(
            200, json={"modalities": {"vision": True, "audio": True}, "model_path": "/m.gguf"}
        )

    async with _client(handler) as client:
        assert await probe_vision("http://llama:8080", client=client) is True
    assert asked == ["http://llama:8080/props"]


async def test_a_text_only_server_reports_no_vision() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"modalities": {"vision": False}})

    async with _client(handler) as client:
        assert await probe_vision("http://llama:8080", client=client) is False


async def test_a_trailing_slash_on_the_endpoint_does_not_double_up() -> None:
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(200, json={"modalities": {"vision": True}})

    async with _client(handler) as client:
        assert await probe_vision("http://llama:8080/", client=client) is True
    assert asked == ["http://llama:8080/props"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"modalities": None},
        {"modalities": []},
        {"modalities": {"vision": "yes"}},
        [1, 2, 3],
    ],
)
async def test_any_other_props_shape_counts_as_no_vision(body: object) -> None:
    # A live server's JSON is that server's to change between versions; a strict read would
    # lose vision on an upgrade, and a lenient one only ever fails closed.
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _client(handler) as client:
        assert await probe_vision("http://llama:8080", client=client) is False


async def test_a_non_2xx_props_counts_as_no_vision() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async with _client(handler) as client:
        assert await probe_vision("http://llama:8080", client=client) is False


async def test_an_unreachable_server_counts_as_no_vision() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        msg = "no route to host"
        raise httpx.ConnectError(msg)

    async with _client(handler) as client:
        assert await probe_vision("http://llama:8080", client=client) is False


async def test_a_props_body_that_is_not_json_counts_as_no_vision() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>oops</html>")

    async with _client(handler) as client:
        assert await probe_vision("http://llama:8080", client=client) is False


async def test_the_probe_owns_a_client_when_none_is_injected() -> None:
    # Production passes no client: the probe runs once at startup, so holding one for the rest
    # of the process would outlive its only use. Nothing listens on this port.
    assert await probe_vision("http://127.0.0.1:1") is False


async def test_on_and_off_never_touch_the_network() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        msg = "the probe must not run when the mode fixes the answer"
        raise AssertionError(msg)

    async with _client(handler) as client:
        assert await vision_enabled("on", "http://llama:8080", client=client) is True
        assert await vision_enabled("off", "http://llama:8080", client=client) is False


async def test_auto_probes() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"modalities": {"vision": True}})

    async with _client(handler) as client:
        assert await vision_enabled("auto", "http://llama:8080", client=client) is True


def test_the_startup_probe_has_a_short_leash() -> None:
    assert PROBE_TIMEOUT_S == 5.0
